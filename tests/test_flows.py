#! /usr/bin/env python3
###############################################################
# SPDX-License-Identifier: BSD-2-Clause-Patent
# SPDX-FileCopyrightText: 2020 the prplMesh contributors (see AUTHORS.md)
# This code is subject to the terms of the BSD+Patent license.
# See LICENSE file for more details.
###############################################################

import argparse
import os
import sys
import time
from typing import Union

import connmap
import environment as env
from capi import tlv
from opts import debug, err, message, opts, status


class TestFlows:
    def __init__(self):
        self.tests = [attr[len('test_'):] for attr in dir(self) if attr.startswith('test_')]
        self.running = ''

    def __fail_no_message(self) -> bool:
        '''Increment failure count and return False.'''
        self.check_error += 1
        if opts.stop_on_failure:
            sys.exit(1)
        return False

    def fail(self, msg: str) -> bool:
        '''Print a red error message, increment failure count and return False.'''
        err('FAIL: {}'.format(msg))
        return self.__fail_no_message()

    def start_test(self, test: str):
        '''Call this at the beginning of a test.'''
        self.running = test
        status(test + " starting")

    def check_log(self, entity_or_radio: Union[env.ALEntity, env.Radio], regex: str,
                  start_line: int = 0) -> bool:
        '''Verify that the logfile for "entity_or_radio" matches "regex", fail if not.'''
        return self.wait_for_log(entity_or_radio, regex, start_line, 0.3)

    def wait_for_log(self, entity_or_radio: Union[env.ALEntity, env.Radio], regex: str,
                     start_line: int, timeout: float) -> bool:
        result, line, match = entity_or_radio.wait_for_log(regex, start_line, timeout)
        if not result:
            self.__fail_no_message()
        return result, line, match

    def run_tests(self, tests):
        '''Run all tests as specified on the command line.'''
        total_errors = 0
        if not tests:
            tests = self.tests
        for test in tests:
            test_full = 'test_' + test
            self.start_test(test)
            env.wired_sniffer.start(test_full)
            self.check_error = 0
            try:
                getattr(self, test_full)()
            finally:
                env.wired_sniffer.stop()
            if self.check_error != 0:
                err(test + " failed")
            else:
                message(test + " OK", 32)
            total_errors += self.check_error
        return total_errors

    # TEST DEFINITIONS #

    def test_initial_ap_config(self):
        '''Check initial configuration on repeater1.'''
        self.check_log(env.agents[0].radios[0], r"WSC Global authentication success")
        self.check_log(env.agents[0].radios[1], r"WSC Global authentication success")
        self.check_log(env.agents[0].radios[0], r"KWA \(Key Wrap Auth\) success")
        self.check_log(env.agents[0].radios[1], r"KWA \(Key Wrap Auth\) success")
        self.check_log(env.agents[0].radios[0],
                       r".* Controller configuration \(WSC M2 Encrypted Settings\)")
        self.check_log(env.agents[0].radios[1],
                       r".* Controller configuration \(WSC M2 Encrypted Settings\)")

    def test_ap_config_renew(self):
        # Regression test: MAC address should be case insensitive
        mac_repeater1_upper = env.agents[0].mac.upper()
        # Configure the controller and send renew
        env.controller.cmd_reply("DEV_RESET_DEFAULT")
        env.controller.cmd_reply(
            "DEV_SET_CONFIG,"
            "bss_info1,{} 8x Multi-AP-24G-1 0x0020 0x0008 maprocks1 0 1,"
            "bss_info2,{} 8x Multi-AP-24G-2 0x0020 0x0008 maprocks2 1 0"
            .format(mac_repeater1_upper, env.agents[0].mac))
        env.controller.dev_send_1905(env.agents[0].mac, 0x000A,
                                     tlv(0x01, 0x0006, "{" + env.controller.mac + "}"),
                                     tlv(0x0F, 0x0001, "{0x00}"),
                                     tlv(0x10, 0x0001, "{0x00}"))

        # Wait a bit for the renew to complete
        time.sleep(3)

        self.check_log(env.agents[0].radios[0],
                       r"Received credentials for ssid: Multi-AP-24G-1 .* bss_type: 2")
        self.check_log(env.agents[0].radios[0],
                       r"Received credentials for ssid: Multi-AP-24G-2 .* bss_type: 1")
        self.check_log(env.agents[0].radios[1], r".* tear down radio")

        bssid1 = env.agents[0].dev_get_parameter('macaddr',
                                                 ruid='0x' +
                                                 env.agents[0].radios[0].mac.replace(':', ''),
                                                 ssid='Multi-AP-24G-1')
        if not bssid1:
            self.fail("repeater1 didn't configure Multi-AP-24G-1")

    def test_ap_config_bss_tear_down(self):
        # Configure the controller and send renew
        env.controller.cmd_reply("DEV_RESET_DEFAULT")
        env.controller.cmd_reply(
            "DEV_SET_CONFIG,bss_info1,"
            "{} 8x Multi-AP-24G-3 0x0020 0x0008 maprocks1 0 1".format(env.agents[0].mac))
        env.controller.dev_send_1905(env.agents[0].mac, 0x000A,
                                     tlv(0x01, 0x0006, "{" + env.controller.mac + "}"),
                                     tlv(0x0F, 0x0001, "{0x00}"),
                                     tlv(0x10, 0x0001, "{0x00}"))

        # Wait a bit for the renew to complete
        time.sleep(3)

        self.check_log(env.agents[0].radios[0],
                       r"Received credentials for ssid: Multi-AP-24G-3 .* bss_type: 2")
        self.check_log(env.agents[0].radios[1], r".* tear down radio")
        conn_map = connmap.get_conn_map()
        repeater1 = conn_map[env.agents[0].mac]
        repeater1_wlan0 = repeater1.radios[env.agents[0].radios[0].mac]
        for vap in repeater1_wlan0.vaps.values():
            if vap.ssid not in (b'Multi-AP-24G-3', b'N/A'):
                self.fail('Wrong SSID: {vap.ssid} instead of Multi-AP-24G-3'.format(vap=vap))
        repeater1_wlan2 = repeater1.radios[env.agents[0].radios[1].mac]
        for vap in repeater1_wlan2.vaps.values():
            if vap.ssid != b'N/A':
                self.fail('Wrong SSID: {vap.ssid} instead torn down'.format(vap=vap))

        # SSIDs have been removed for the CTT Agent1's front radio
        env.controller.cmd_reply(
            "DEV_SET_CONFIG,bss_info1,{} 8x".format(env.agents[0].mac))
        # Send renew message
        env.controller.dev_send_1905(env.agents[0].mac, 0x000A,
                                     tlv(0x01, 0x0006, "{" + env.controller.mac + "}"),
                                     tlv(0x0F, 0x0001, "{0x00}"),
                                     tlv(0x10, 0x0001, "{0x00}"))

        time.sleep(3)
        self.check_log(env.agents[0].radios[0], r".* tear down radio")
        conn_map = connmap.get_conn_map()
        repeater1 = conn_map[env.agents[0].mac]
        repeater1_wlan0 = repeater1.radios[env.agents[0].radios[0].mac]
        for vap in repeater1_wlan0.vaps.values():
            if vap.ssid != b'N/A':
                self.fail('Wrong SSID: {vap.ssid} instead torn down'.format(vap=vap))
        repeater1_wlan2 = repeater1.radios[env.agents[0].radios[1].mac]
        for vap in repeater1_wlan2.vaps.values():
            if vap.ssid != b'N/A':
                self.fail('Wrong SSID: {vap.ssid} instead torn down'.format(vap=vap))

    def test_channel_selection(self):
        debug("Send channel preference query")
        env.controller.dev_send_1905(env.agents[0].mac, 0x8004)
        time.sleep(1)
        debug("Confirming channel preference query has been received on agent")
        self.check_log(env.agents[0].radios[0], "CHANNEL_PREFERENCE_QUERY_MESSAGE")
        self.check_log(env.agents[0].radios[1], "CHANNEL_PREFERENCE_QUERY_MESSAGE")

        debug("Send empty channel selection request")
        cs_req_mid = env.controller.dev_send_1905(env.agents[0].mac,
                                                  0x8006, tlv(0x00, 0x0000, "{}"))
        time.sleep(1)

        debug("Confirming channel selection request has been received on controller")
        self.check_log(env.controller,
                       r"CHANNEL_SELECTION_RESPONSE_MESSAGE, mid={}".format(cs_req_mid))

        debug("Confirming empty channel selection request has been received on agent")
        self.check_log(env.agents[0].radios[0], "CHANNEL_SELECTION_REQUEST_MESSAGE")
        self.check_log(env.agents[0].radios[1], "CHANNEL_SELECTION_REQUEST_MESSAGE")

        debug("Confirming OPERATING_CHANNEL_REPORT_MESSAGE message has been received on \
            controller with mid")

        result, ocrm_line, mid_match = self.check_log(
            env.controller,
            r'.+OPERATING_CHANNEL_REPORT_MESSAGE,\smid=(\d+)'
        )
        if (mid_match):
            debug("Confirming ACK_MESSAGE from the controller \
                with same mid as OPERATING_CHANNEL_REPORT_MESSAGE")
            self.check_log(env.agents[0].radios[0], "ACK_MESSAGE, mid={}".format(mid_match[0]))
            self.check_log(env.agents[0].radios[1], "ACK_MESSAGE, mid={}".format(mid_match[0]))

        tp20dBm = 0x14
        tp21dBm = 0x15

        for payload_transmit_power in (tp20dBm, tp21dBm):
            debug("Send empty channel selection request with changing tx_power_limit")
            cs_req_mid = env.controller.dev_send_1905(
                env.agents[0].mac,
                0x8006,
                tlv(0x8D, 0x0007, '{} 0x{:02x}'.format(env.agents[0].radios[0].mac,
                                                       payload_transmit_power)),
                tlv(0x8D, 0x0007, '{} 0x{:02x}'.format(env.agents[0].radios[1].mac,
                                                       payload_transmit_power))
            )
            time.sleep(1)

            self.check_log(env.controller,
                           r"CHANNEL_SELECTION_RESPONSE_MESSAGE, mid={}".format(cs_req_mid))

            self.check_log(env.agents[0].radios[0], "CHANNEL_SELECTION_REQUEST_MESSAGE")
            self.check_log(env.agents[0].radios[1], "CHANNEL_SELECTION_REQUEST_MESSAGE")

            self.check_log(env.agents[0].radios[0],
                           "tlvTransmitPowerLimit {}".format(payload_transmit_power))
            self.check_log(env.agents[0].radios[1],
                           "tlvTransmitPowerLimit {}".format(payload_transmit_power))

            self.check_log(env.controller, "tx_power={}".format(payload_transmit_power))

            result, ocrm_line, mid_match = self.check_log(
                env.controller,
                r'.+OPERATING_CHANNEL_REPORT_MESSAGE,\smid=(\d+)',
                ocrm_line
            )
            if (result):
                self.check_log(env.agents[0].radios[0], "ACK_MESSAGE, mid={}".format(mid_match[0]))

                self.check_log(env.agents[0].radios[1], "ACK_MESSAGE, mid={}".format(mid_match[0]))

        # payload_wlan0 - request for change channel on 6
        payload_wlan0 = (
            "0x14 "
            "{0x51 {0x0C {0x01 0x02 0x03 0x04 0x05 0x07 0x08 0x09 0x0A 0x0B 0x0C 0x0D} 0x00}} "
            "{0x52 {0x00 0x00}} "
            "{0x53 {0x08 {0x01 0x02 0x03 0x04 0x05 0x07 0x08 0x09} 0x00}} "
            "{0x54 {0x08 {0x05 0x07 0x08 0x09 0x0A 0x0B 0x0C 0x0D} 0x00}} "
            "{0x73 {0x00 0x00}} "
            "{0x74 {0x00 0x00}} "
            "{0x75 {0x00 0x00}} "
            "{0x76 {0x00 0x00}} "
            "{0x77 {0x00 0x00}} "
            "{0x78 {0x00 0x00}} "
            "{0x79 {0x00 0x00}} "
            "{0x7A {0x00 0x00}} "
            "{0x7B {0x00 0x00}} "
            "{0x7C {0x00 0x00}} "
            "{0x7D {0x00 0x00}} "
            "{0x7E {0x00 0x00}} "
            "{0x7F {0x00 0x00}} "
            "{0x80 {0x00 0x00}} "
            "{0x81 {0x00 0x00}} "
            "{0x82 {0x00 0x00}} "
        )

        # payload_wlan2  - request for change channel on 36
        payload_wlan2 = (
            "0x14 "
            "{0x51 {0x00 0x00}} "
            "{0x52 {0x00 0x00}} "
            "{0x53 {0x00 0x00}} "
            "{0x54 {0x00 0x00}} "
            "{0x73 0x03 {0x28 0x2C 0x30} 0x00} "
            "{0x74 0x01 {0x2C} 0x00} "
            "{0x75 {0x00 0x00}} "
            "{0x76 {0x00 0x00}} "
            "{0x77 {0x00 0x00}} "
            "{0x78 {0x00 0x00}} "
            "{0x79 {0x00 0x00}} "
            "{0x7A {0x00 0x00}} "
            "{0x7B {0x00 0x00}} "
            "{0x7C {0x00 0x00}} "
            "{0x7D {0x00 0x00}} "
            "{0x7E {0x00 0x00}} "
            "{0x7F {0x00 0x00}} "
            "{0x80 0x05 {0x3A 0x6A 0x7A 0x8A 0x9B} 0x00} "
            "{0x81 {0x00 0x00}} "
            "{0x82 {0x00 0x00}}"
        )

        """
        Step 1: Trigger channel selection to channel 6 and 36. Check that
                operating channel report was sent.

        Step 2: Trigger channel selection to channel 6 and 36 again - check that
                operating channel report is sent again. This is to catch bugs
                when we don't send channel report when there is no need to
                switch channel
        """
        for i in range(1, 3):
            debug("Send channel selection request, step {}".format(i))
            mid = env.controller.dev_send_1905(
                env.agents[0].mac,
                0x8006,
                tlv(0x8B, 0x005F, '{} {}'.format(env.agents[0].radios[0].mac, payload_wlan0)),
                tlv(0x8D, 0x0007, '{} 0x{:2x}'.format(env.agents[0].radios[0].mac, tp20dBm)),
                tlv(0x8B, 0x004C, '{} {}'.format(env.agents[0].radios[1].mac, payload_wlan2)),
                tlv(0x8D, 0x0007, '{} 0x{:2x}'.format(env.agents[0].radios[1].mac, tp20dBm))
            )
            time.sleep(1)

            debug(
                "Confirming channel selection request has been received on controller,\
                    step {}".format(i))
            self.check_log(env.controller,
                           r"CHANNEL_SELECTION_RESPONSE_MESSAGE, mid={}".format(mid))

            debug(
                "Confirming channel selection request has been received on agent,step {}".format(i))

            self.check_log(env.agents[0].radios[0], "CHANNEL_SELECTION_REQUEST_MESSAGE")
            self.check_log(env.agents[0].radios[1], "CHANNEL_SELECTION_REQUEST_MESSAGE")

            debug(
                "Confirming tlvTransmitPowerLimit has been received with correct value on \
                    agent, step {}".format(i))

            self.check_log(env.agents[0].radios[0], "tlvTransmitPowerLimit {}".format(tp20dBm))

            self.check_log(env.agents[0].radios[0],
                           "ACTION_APMANAGER_HOSTAP_CHANNEL_SWITCH_ACS_START")

            self.check_log(env.agents[0].radios[1], "tlvTransmitPowerLimit {}".format(tp20dBm))

            self.check_log(env.agents[0].radios[0],
                           "ACTION_APMANAGER_HOSTAP_CHANNEL_SWITCH_ACS_START")

            debug("Confirming CHANNEL_SELECTION_RESPONSE_MESSAGE has been received, \
                step {}".format(i))

            self.check_log(env.controller, "CHANNEL_SELECTION_RESPONSE_MESSAGE")

            debug("Confirming OPERATING_CHANNEL_REPORT_MESSAGE has been received on \
                controller step {}".format(i))

            result, ocrm_line, mid_match = self.check_log(
                env.controller,
                r'.+OPERATING_CHANNEL_REPORT_MESSAGE,\smid=(\d+)',
                ocrm_line)

            if (mid_match):
                self.check_log(env.agents[0].radios[0],
                               "ACK_MESSAGE, mid={}".format(mid_match[0]))

                self.check_log(env.agents[0].radios[1],
                               "ACK_MESSAGE, mid={}".format(mid_match[0]))

            debug("Confirming tx_power has been received with correct value on controller, \
                step {}".format(i))
            self.check_log(env.controller, "tx_power={}".format(tp20dBm))

    def test_ap_capability_query(self):
        env.controller.dev_send_1905(env.agents[0].mac, 0x8001)
        time.sleep(1)

        debug("Confirming ap capability query has been received on agent")
        self.check_log(env.agents[0], "AP_CAPABILITY_QUERY_MESSAGE")

        debug("Confirming ap capability report has been received on controller")
        self.check_log(env.controller, "AP_CAPABILITY_REPORT_MESSAGE")

    def test_link_metric_query(self):
        env.controller.dev_send_1905(env.agents[0].mac, 0x0005,
                                     tlv(0x08, 0x0002, "0x00 0x02"))
        time.sleep(1)

        debug("Confirming link metric query has been received on agent")
        self.check_log(env.agents[0], "Received LINK_METRIC_QUERY_MESSAGE")

        debug("Confirming link metric response has been received on controller")
        self.check_log(env.controller, "Received LINK_METRIC_RESPONSE_MESSAGE")
        self.check_log(env.controller, "Received TLV_TRANSMITTER_LINK_METRIC")
        self.check_log(env.controller, "Received TLV_RECEIVER_LINK_METRIC")

    def test_combined_infra_metrics(self):
        debug("Send AP Metrics query message to agent 1")
        env.controller.dev_send_1905(env.agents[0].mac, 0x800B,
                                     tlv(0x93, 0x0007, "0x01 {%s}" % (env.agents[0].radios[0].mac)))
        self.check_log(env.agents[0].radios[0], "Received AP_METRICS_QUERY_MESSAGE")
        # TODO agent should send response autonomously, with same MID.
        # AP metrics TLV
        tlv1 = tlv(0x94, 0x000d, "{%s} 0x01 0x0002 0x01 0x1f2f3f" % (env.agents[0].radios[0].mac))
        # STA metrics TLV with no metrics
        tlv2 = tlv(0x96, 0x0007, "{55:44:33:22:11:00} 0x00")
        # STA metrics TLV for STA connected to this BSS
        tlv3 = tlv(0x96, 0x001a,
                   "{66:44:33:22:11:00} 0x01 {%s} 0x11223344 0x1a2a3a4a 0x1b2b3b4b 0x55" % env.agents[0].radios[0].mac)  # noqa E501
        # STA traffic stats TLV for same STA
        tlv4 = tlv(0xa2, 0x0022,
                   "{55:44:33:22:11:00} 0x10203040 0x11213141 0x12223242 0x13233343 0x14243444 0x15253545 0x16263646")  # noqa E501
        env.agents[0].dev_send_1905(env.controller.mac, 0x800C, tlv1, tlv2, tlv3, tlv4)
        self.check_log(env.controller, "Received AP_METRICS_RESPONSE_MESSAGE")

        debug("Send AP Metrics query message to agent 2")
        env.controller.dev_send_1905(env.agents[1].mac, 0x800B,
                                     tlv(0x93, 0x0007, "0x01 {%s}" % env.agents[1].radios[1].mac))
        self.check_log(env.agents[1].radios[1], "Received AP_METRICS_QUERY_MESSAGE")
        # TODO agent should send response autonomously
        # Same as above but with different STA MAC addresses, different values and
        # skipping the empty one
        tlv1 = tlv(0x94, 0x000d, "{%s} 0x01 0x0002 0x01 0x1f2f3f" % (env.agents[1].radios[1].mac))
        tlv3 = tlv(0x96, 0x001a,
                   "{77:44:33:22:11:00} 0x01 {%s} 0x19293949 0x10203040 0x11213141 0x99" % env.agents[1].radios[1].mac)  # noqa E501
        tlv4 = tlv(0xa2, 0x0022,
                   "{77:44:33:22:11:00} 0xa0203040 0xa1213141 0xa2223242 0xa3233343 0xa4243444 0xa5253545 0xa6263646")  # noqa E501
        env.agents[1].dev_send_1905(env.controller.mac, 0x800C, tlv1, tlv3, tlv4)
        self.check_log(env.controller, "Received AP_METRICS_RESPONSE_MESSAGE")

        debug("Send 1905 Link metric query to agent 1 (neighbor gateway)")
        env.controller.dev_send_1905(env.agents[0].mac, 0x0005,
                                     tlv(0x08, 0x0008, "0x01 {%s} 0x02" % env.controller.mac))
        self.check_log(env.agents[0], "Received LINK_METRIC_QUERY_MESSAGE")
        self.check_log(env.controller, "Received LINK_METRIC_RESPONSE_MESSAGE")
        self.check_log(env.controller, "Received TLV_TRANSMITTER_LINK_METRIC")
        self.check_log(env.controller, "Received TLV_RECEIVER_LINK_METRIC")

        # Trigger combined infra metrics
        debug("Send Combined infrastructure metrics message to agent 1")
        env.controller.dev_send_1905(env.agents[0].mac, 0x8013)
        self.check_log(env.agents[0], "Received COMBINED_INFRASTRUCTURE_METRICS")
        self.check_log(env.agents[0], "Received TLV_TRANSMITTER_LINK_METRIC")
        self.check_log(env.agents[0], "Received TLV_RECEIVER_LINK_METRIC")

    def test_client_capability_query(self):
        sta1 = env.Station.create()
        sta2 = env.Station.create()

        debug("Send client capability query for unconnected STA")
        env.controller.dev_send_1905(env.agents[0].mac, 0x8009,
                                     tlv(0x90, 0x000C,
                                         '{} {}'.format(env.agents[0].radios[0].mac, sta1.mac)))
        time.sleep(1)
        debug("Confirming client capability query has been received on agent")
        # check that both radio agents received it, in the future we'll add a check to verify which
        # radio the query was intended for.
        self.check_log(env.agents[0], r"CLIENT_CAPABILITY_QUERY_MESSAGE")

        debug("Confirming client capability report message has been received on controller")
        self.check_log(env.controller, r"Received CLIENT_CAPABILITY_REPORT_MESSAGE")
        self.check_log(env.controller,
                       r"Result Code= FAILURE, client MAC= {}, BSSID= {}"
                       .format(sta1.mac, env.agents[0].radios[0].mac))

        debug("Connect dummy STA to wlan0")
        env.agents[0].radios[0].vaps[0].associate(sta2)

        debug("Send client capability query for connected STA")
        env.controller.dev_send_1905(env.agents[0].mac, 0x8009,
                                     tlv(0x90, 0x000C,
                                         '{} {}'.format(env.agents[0].radios[0].mac, sta2.mac)))
        time.sleep(1)

        debug("Confirming client capability report message has been received on controller")
        self.check_log(env.controller, r"Received CLIENT_CAPABILITY_REPORT_MESSAGE")
        self.check_log(env.controller,
                       r"Result Code= SUCCESS, client MAC= {}, BSSID= {}"
                       .format(sta2.mac, env.agents[0].radios[0].mac))

    def test_client_association_dummy(self):
        sta = env.Station.create()

        debug("Connect dummy STA to wlan0")
        env.agents[0].radios[0].vaps[0].associate(sta)
        debug("Send client association control request to the chosen BSSID (UNBLOCK)")
        env.beerocks_cli_command('client_allow {} {}'.format(sta.mac, env.agents[0].radios[1].mac))
        time.sleep(1)

        debug("Confirming Client Association Control Request message was received (UNBLOCK)")
        self.check_log(env.agents[0].radios[1], r"Got client allow request for {}".format(sta.mac))

        debug("Send client association control request to all other (BLOCK) ")
        env.beerocks_cli_command('client_disallow {} {}'.format(sta.mac,
                                                                env.agents[0].radios[0].mac))
        time.sleep(1)

        debug("Confirming Client Association Control Request message was received (BLOCK)")
        self.check_log(env.agents[0].radios[0],
                       r"Got client disallow request for {}".format(sta.mac))

    def test_client_steering_mandate(self):
        debug("Send topology request to agent 1")
        env.controller.dev_send_1905(env.agents[0].mac, 0x0002)
        time.sleep(1)
        debug("Confirming topology query was received")
        self.check_log(env.agents[0], "TOPOLOGY_QUERY_MESSAGE")

        debug("Send topology request to agent 2")
        env.controller.dev_send_1905(env.agents[1].mac, 0x0002)
        time.sleep(1)
        debug("Confirming topology query was received")
        self.check_log(env.agents[1], "TOPOLOGY_QUERY_MESSAGE")

        debug("Send Client Steering Request message for Steering Mandate to CTT Agent1")
        env.controller.dev_send_1905(env.agents[0].mac, 0x8014,
                                       tlv(0x9B, 0x001b,
                                           "{%s 0xe0 0x0000 0x1388 0x01 {0x000000110022} 0x01 {%s 0x73 0x24}}" % (env.agents[0].radios[0].mac, env.agents[1].radios[0].mac)))  # noqa E501
        time.sleep(1)
        debug("Confirming Client Steering Request message was received - mandate")
        self.check_log(env.agents[0].radios[0], "Got steer request")

        debug("Confirming BTM Report message was received")
        self.check_log(env.controller, "CLIENT_STEERING_BTM_REPORT_MESSAGE")

        debug("Checking BTM Report source bssid")
        self.check_log(env.controller, "BTM_REPORT from source bssid %s" %
                       env.agents[0].radios[0].mac)

        debug("Confirming ACK message was received")
        self.check_log(env.agents[0].radios[0], "ACK_MESSAGE")

        env.controller.dev_send_1905(env.agents[0].mac, 0x8014,
                                       tlv(0x9B, 0x000C,
                                           "{%s 0x00 0x000A 0x0000 0x00}" % env.agents[0].radios[0].mac))  # noqa E501
        time.sleep(1)
        debug("Confirming Client Steering Request message was received - Opportunity")
        self.check_log(env.agents[0].radios[0], "CLIENT_STEERING_REQUEST_MESSAGE")

        debug("Confirming ACK message was received")
        self.check_log(env.controller, "ACK_MESSAGE")

        debug("Confirming steering completed message was received")
        self.check_log(env.controller, "STEERING_COMPLETED_MESSAGE")

        debug("Confirming ACK message was received")
        self.check_log(env.agents[0].radios[0], "ACK_MESSAGE")

    def test_client_steering_dummy(self):
        sta = env.Station.create()

        debug("Connect dummy STA to wlan0")
        env.agents[0].radios[0].vaps[0].associate(sta)
        debug("Send steer request ")
        env.beerocks_cli_command("steer_client {} {}".format(sta.mac, env.agents[0].radios[1].mac))
        time.sleep(1)

        debug("Confirming Client Association Control Request message was received (UNBLOCK)")
        self.check_log(env.agents[0].radios[1], r"Got client allow request")

        debug("Confirming Client Association Control Request message was received (BLOCK)")
        self.check_log(env.agents[0].radios[0], r"Got client disallow request")

        debug("Confirming Client Association Control Request message was received (BLOCK)")
        self.check_log(env.agents[1].radios[0], r"Got client disallow request")

        debug("Confirming Client Association Control Request message was received (BLOCK)")
        self.check_log(env.agents[1].radios[1], r"Got client disallow request")

        debug("Confirming Client Steering Request message was received - mandate")
        self.check_log(env.agents[0].radios[0], r"Got steer request")

        debug("Confirming BTM Report message was received")
        self.check_log(env.controller, r"CLIENT_STEERING_BTM_REPORT_MESSAGE")

        debug("Confirming ACK message was received")
        self.check_log(env.agents[0].radios[0], r"ACK_MESSAGE")

        debug("Disconnect dummy STA from wlan0")
        env.agents[0].radios[0].vaps[0].disassociate(sta)
        # Make sure that controller sees disconnect before connect by waiting a little
        time.sleep(1)

        debug("Connect dummy STA to wlan2")
        env.agents[0].radios[1].vaps[0].associate(sta)
        debug("Confirm steering success by client connected")
        self.check_log(env.controller, r"steering successful for sta {}".format(sta.mac))
        self.check_log(env.controller,
                       r"sta {} disconnected due to steering request".format(sta.mac))

        # Make sure that all blocked agents send UNBLOCK messages at the end of
        # disallow period (default 25 sec)
        time.sleep(25)

        debug("Confirming Client Association Control Request message was received (UNBLOCK)")
        self.check_log(env.agents[0].radios[0], r"Got client allow request")

        debug("Confirming Client Association Control Request message was received (UNBLOCK)")
        self.check_log(env.agents[1].radios[0], r"Got client allow request")

        debug("Confirming Client Association Control Request message was received (UNBLOCK)")
        self.check_log(env.agents[1].radios[1], r"Got client allow request")

    def test_client_steering_policy(self):
        debug("Send client steering policy to agent 1")
        mid = env.controller.dev_send_1905(env.agents[0].mac, 0x8003,
                                             tlv(0x89, 0x000C, "{0x00 0x00 0x01 {0x112233445566 0x01 0xFF 0x14}}"))  # noqa E501
        time.sleep(1)
        debug("Confirming client steering policy has been received on agent")

        self.check_log(env.agents[0].radios[0], r"MULTI_AP_POLICY_CONFIG_REQUEST_MESSAGE")
        time.sleep(1)
        debug("Confirming client steering policy ack message has been received on the controller")
        self.check_log(env.controller, r"ACK_MESSAGE, mid=0x{:04x}".format(mid))

    def test_client_association(self):
        debug("Send topology request to agent 1")
        env.controller.dev_send_1905(env.agents[0].mac, 0x0002)
        debug("Confirming topology query was received")
        self.check_log(env.agents[0], r"TOPOLOGY_QUERY_MESSAGE")

        debug("Send client association control message")
        env.controller.dev_send_1905(env.agents[0].mac, 0x8016,
                                       tlv(0x9D, 0x000F,
                                           "{%s 0x00 0x1E 0x01 {0x000000110022}}" % env.agents[0].radios[0].mac))  # noqa E501

        debug("Confirming client association control message has been received on agent")
        # check that both radio agents received it,in the future we'll add a check to verify which
        # radio the query was intended for.
        self.check_log(env.agents[0].radios[0], r"CLIENT_ASSOCIATION_CONTROL_REQUEST_MESSAGE")
        self.check_log(env.agents[0].radios[1], r"CLIENT_ASSOCIATION_CONTROL_REQUEST_MESSAGE")

        debug("Confirming ACK message was received on controller")
        self.check_log(env.controller, r"ACK_MESSAGE")

    def test_higher_layer_data_payload_trigger(self):
        mac_gateway_hex = '0x' + env.controller.mac.replace(':', '')
        debug("mac_gateway_hex = " + mac_gateway_hex)
        payload = 199 * (mac_gateway_hex + " ") + mac_gateway_hex

        debug("Send Higher Layer Data message")
        # MCUT sends Higher Layer Data message to CTT Agent1 by providing:
        # Higher layer protocol = "0x00"
        # Higher layer payload = 200 concatenated copies of the ALID of the MCUT (1200 octets)
        mid = env.controller.dev_send_1905(env.agents[0].mac, 0x8018,
                                           tlv(0xA0, 0x04b1, "{0x00 %s}" % payload))

        debug("Confirming higher layer data message was received in the agent")

        self.check_log(env.agents[0], r"HIGHER_LAYER_DATA_MESSAGE")

        debug("Confirming matching protocol and payload length")

        self.check_log(env.agents[0], r"protocol: 0")
        self.check_log(env.agents[0], r"payload_length: 0x4b0")

        debug("Confirming ACK message was received in the controller")
        self.check_log(env.controller, r"ACK_MESSAGE, mid=0x{:04x}".format(mid))

    def test_topology(self):
        mid = env.controller.dev_send_1905(env.agents[0].mac, 0x0002)
        debug("Confirming topology query was received")
        self.check_log(env.agents[0], r"TOPOLOGY_QUERY_MESSAGE.*mid={:d}".format(mid))


if __name__ == '__main__':
    t = TestFlows()

    parser = argparse.ArgumentParser()
    parser.add_argument("--tcpdump", "-t", action='store_true', default=False,
                        help="capture the packets during each test")
    parser.add_argument("--verbose", "-v", action='store_true', default=False,
                        help="report each action")
    parser.add_argument("--stop-on-failure", "-s", action='store_true', default=False,
                        help="exit on the first failure")
    user = os.getenv("SUDO_USER", os.getenv("USER", ""))
    parser.add_argument("--unique-id", "-u", type=str, default=user,
                        help="append UNIQUE_ID to all container names, e.g. gateway-<UNIQUE_ID>; "
                             "defaults to {}".format(user))
    parser.add_argument("--skip-init", action='store_true', default=False,
                        help="don't start up the containers")
    parser.add_argument("tests", nargs='*',
                        help="tests to run; if not specified, run all tests: " + ", ".join(t.tests))
    options = parser.parse_args()

    unknown_tests = [test for test in options.tests if test not in t.tests]
    if unknown_tests:
        parser.error("Unknown tests: {}".format(', '.join(unknown_tests)))

    opts.verbose = options.verbose
    opts.tcpdump = options.tcpdump

    opts.tcpdump_dir = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), '..', 'logs'))
    opts.stop_on_failure = options.stop_on_failure

    t.start_test('init')
    env.launch_environment_docker(options.unique_id, options.skip_init)

    if t.run_tests(options.tests):
        sys.exit(1)
