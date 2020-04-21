# Introduction

Current testing scheme is partially virtual.
All test are done in so-called "dummy" mode.
This mode operates without any interaction with WiFi device.
Recently, the number of cases, when issue caused by changes wasn't detected by regular testing (using `test_flows.py`) but noticed during nightly testbed test, has increased.
Yet, we don't have any means to provide automated testing on real hardware.
So temporarily, all developers were forced to manually trigger testbed testing for each PR published as part of regular flow.
CI has only one testbed set up available, so we can perform only single test at same moment.
Also, testbed is able to perform only Cerification tests.
We are interested in wider test scenarios, which cover project-specific bugs, corner cases and etc.

Due to limitations of current testing approach, need of automated tests on real hardware raises.
In order to speed up development process, it was decided by community to use [boardfarm](https://github.com/mattsm/boardfarm/) as a base for automated testing.
This project can provide us with basic infrastructure for tests and save effort in terms of development and support.
For details about integration process, design please see next sections.

# Design

By itself, [boardfarm](https://github.com/mattsm/boardfarm/) provides us with:
1. Abstraction of test set-up
1. Provides some basic classes of devices
1. Some simple tests
1. Handles connections to boards
1. Provides test-suite organisation

[boardfarm](https://github.com/mattsm/boardfarm/) already has some representation of some general devices (like Linux, OpenWRT device).
But our test flows involve more components and require more info about devices\[1\].
So we have to expand base classes with representation of `prplWRT` devices capable handling Agent, Controller and Sniffer.
Also, some additional abstraction of easyMesh specific entities may ease future work(like CAPI, IEEE1905.1 message).

Hierarchy of devices, entities their relation can be understood easier using typical test set-up scheme provided below:

![test setup](/documentation/images/plantuml/boardfarm_prplMesh_test_setup.png)

Please, note.
In general case, it's expected that prplMesh executables are delivered to DUT (device under test) as OpenWRT `*.ipk`.
DUT should be already burn with prplWRT or other supported platform.
Thus, LAN connection required for flashing in uboot mode is missing from the scheme.

In general, in order to start using [boardfarm](https://github.com/mattsm/boardfarm/) we have to create:

1. Devices
	1. prplWRT
	1. dockerized dummy device
	1. Wired sniffer
	1. Wireless sniffer
1. Additional entities
	1. CAPI
	1. prplMesh_controller
	1. prplMesh_agent
	1. prplMesh_radio_dummy
	1. prplMesh_radio_hw

Relations between classes and their hierarchy displayed below:


![Classes scheme](/documentation/images/plantuml/boardfarm_prplMesh_classes.png)


Please, note.
That scheme is general and do not includes *all* methods and *fields*.
If you are interested in them, please see source code.

This additional infrastructure should be enough to start porting already existing tests from `test_flows.py`.

## Integration

[boardfarm](https://github.com/mattsm/boardfarm/) itself supports plugins\[2\].
It allows to embed code to [boardfarm](https://github.com/mattsm/boardfarm/) which isn't present in main repository.
All device classes, test specific entities and tests itself should be included like this.
When they are stable enough, it's expected to push that to original [boardfarm](https://github.com/mattsm/boardfarm/) repository.

General integration steps:

1. Deliver boardfarm along with prplMesh.
1. Create infrastructure.
1. Move all tests from `test_flows.py`.
1. Form boardfarm configuration for CI set up.
1. Set up GitLab CI to trigger tests on PR merge.

# References

\[1\] Test flows [documentation](../tests/README.md).  
\[2\] [Commit](https://github.com/mattsm/boardfarm/commits/c21979e89536a850f406d4621bb6024e7968cd48) which replaces `BFT_OVERLAY` with plugins functionality.  
