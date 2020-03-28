#! /usr/bin/env python3
###############################################################
# SPDX-License-Identifier: BSD-2-Clause-Patent
# Copyright (c) 2020 Tomer Eliyahu (Intel)
# This code is subject to the terms of the BSD+Patent license.
# See LICENSE file for more details.
###############################################################

import argparse
import xlsxwriter

class LogsParser:
    '''Parses certification logs folder.'''
    def __init__(self, path: str):
        self.path = path

class Report:
    '''Excel report generator.'''
    def __init__(self, path: str):
        self.path = path
        self.data = [
            ['Apples', 10000, 5000, 8000, 6000],
            ['Pears', 2000, 3000, 4000, 5000],
            ['Bananas', 6000, 6000, 6500, 6000],
            ['Oranges', 500, 300, 200, '=HYPERLINK("https://ftp.essensium.com/owncloud/index.php/apps/files/?dir=/prplmesh/certification/Nightly/agent_certification/2020-03-25_20-30-29/PASS/MAP-4.3.1_ETH", "LOGS LINK             2")'],
        ]
        self.workbook = xlsxwriter.Workbook('tables.xlsx')
        self.worksheet = self.workbook.add_worksheet()

    def generate(self):
        self.set_column_width()
        self.worksheet.add_table('B3:F7', {'data': self.data,
                              'columns': [{'header': 'Test'},
                                          {'header': 'Subtest'},
                                          {'header': 'DUT'},
                                          {'header': 'Result'},
                                          {'header': 'Logs'},
                                          ]})
        self.workbook.close()

if __name__ == '__main__':
    report = Report("/home/tester/work/report.xls")
    report.generate()