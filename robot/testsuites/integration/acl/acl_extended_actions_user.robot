*** Settings ***
Variables    common.py

Library      utility_keywords.py

Resource     common_steps_acl_extended.robot
Resource     payment_operations.robot
Resource     setup_teardown.robot
Resource     eacl_tables.robot

*** Test cases ***
Extended ACL Operations
    [Documentation]         Testcase to validate NeoFS operations with extended ACL.
    [Tags]                  ACL  eACL
    [Timeout]               20 min


    ${WALLET}   ${_}     ${_} =   Prepare Wallet And Deposit

                            Log    Check extended ACL with simple object
    ${FILE_S}    ${_} =     Generate file    ${SIMPLE_OBJ_SIZE}
                            Check eACL Deny and Allow All User    ${WALLET}

                            Log    Check extended ACL with complex object
    ${FILE_S}    ${_} =     Generate file    ${COMPLEX_OBJ_SIZE}
                            Check eACL Deny and Allow All User    ${WALLET}



*** Keywords ***

Check eACL Deny and Allow All User
    [Arguments]             ${WALLET}
                            Check eACL Deny and Allow All    ${WALLET}    ${EACL_DENY_ALL_USER}    ${EACL_ALLOW_ALL_USER}    ${WALLET}
