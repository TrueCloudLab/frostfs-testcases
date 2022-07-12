*** Settings ***
Variables    common.py

Library      utility_keywords.py

Resource     common_steps_acl_extended.robot
Resource     payment_operations.robot
Resource     eacl_tables.robot

*** Test cases ***
Extended ACL Operations
    [Documentation]         Testcase to validate NeoFS operations with extended ACL with Other group key.
    [Tags]                  ACL  eACL  NeoFS  NeoCLI
    [Timeout]               20 min


    ${WALLET}   ${_}     ${_} =   Prepare Wallet And Deposit
    ${WALLET_OTH}   ${_}     ${_} =   Prepare Wallet And Deposit

                            Log    Check extended ACL with simple object
    ${FILE_S}    ${_} =     Generate file    ${SIMPLE_OBJ_SIZE}
                            Check eACL Deny and Allow All Other    ${WALLET}    ${WALLET_OTH}

                            Log    Check extended ACL with complex object
    ${FILE_S}    ${_} =     Generate file    ${COMPLEX_OBJ_SIZE}
                            Check eACL Deny and Allow All Other    ${WALLET}    ${WALLET_OTH}



*** Keywords ***

Check eACL Deny and Allow All Other
    [Arguments]    ${WALLET}    ${WALLET_OTH}
                            Check eACL Deny and Allow All    ${WALLET_OTH}    ${EACL_DENY_ALL_OTHERS}    ${EACL_ALLOW_ALL_OTHERS}    ${WALLET}