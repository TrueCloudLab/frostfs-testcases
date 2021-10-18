*** Settings ***
Variables       ../../../variables/common.py
Library         ../${RESOURCES}/neofs.py
Library         ../${RESOURCES}/payment_neogo.py

Resource        common_steps_acl_basic.robot
Resource        ../${RESOURCES}/payment_operations.robot
Resource        ../${RESOURCES}/setup_teardown.robot


*** Test cases ***
Basic ACL Operations for Private Container
    [Documentation]         Testcase to validate NeoFS operations with ACL for Private Container.
    [Tags]                  ACL  NeoFS  NeoCLI
    [Timeout]               20 min

    [Setup]                 Setup

    ${WALLET}   ${ADDR}     ${USER_KEY} =   Prepare Wallet And Deposit
    ${WALLET_OTH}   ${ADDR_OTH}     ${OTHER_KEY} =   Prepare Wallet And Deposit

    ${PRIV_CID} =           Create Private Container    ${USER_KEY}
    ${FILE_S}    ${FILE_S_HASH} =                        Generate file    ${SIMPLE_OBJ_SIZE}
                            Check Private Container    ${USER_KEY}    ${FILE_S}    ${PRIV_CID}    ${OTHER_KEY}

    ${PRIV_CID} =           Create Private Container    ${USER_KEY}
    ${FILE_S}    ${FILE_S_HASH} =             Generate file    ${COMPLEX_OBJ_SIZE}
                            Check Private Container    ${USER_KEY}    ${FILE_S}    ${PRIV_CID}    ${OTHER_KEY}

    [Teardown]              Teardown    acl_basic_private_container




*** Keywords ***

Check Private Container
    [Arguments]    ${USER_KEY}    ${FILE_S}    ${PRIV_CID}    ${OTHER_KEY}

    # Put
    ${S_OID_USER} =         Put object                 ${USER_KEY}         ${FILE_S}    ${PRIV_CID}    ${EMPTY}    ${EMPTY}
                            Run Keyword And Expect Error        *
                            ...  Put object            ${OTHER_KEY}        ${FILE_S}    ${PRIV_CID}    ${EMPTY}    ${EMPTY}
                            Run Keyword And Expect Error        *
                            ...  Put object            ${NEOFS_IR_WIF}    ${FILE_S}    ${PRIV_CID}    ${EMPTY}    ${EMPTY}
    ${S_OID_SYS_SN} =       Put object                 ${NEOFS_SN_WIF}    ${FILE_S}    ${PRIV_CID}    ${EMPTY}    ${EMPTY}

    # Get
                            Get object               ${USER_KEY}         ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}      s_file_read
                            Run Keyword And Expect Error        *
                            ...  Get object          ${OTHER_KEY}        ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}      s_file_read
                            Get object               ${NEOFS_IR_WIF}    ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}      s_file_read
                            Get object               ${NEOFS_SN_WIF}    ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}      s_file_read

    # Get Range
                            Get Range                           ${USER_KEY}         ${PRIV_CID}    ${S_OID_USER}    s_get_range    ${EMPTY}    0:256
                            Run Keyword And Expect Error        *
                            ...  Get Range                      ${OTHER_KEY}        ${PRIV_CID}    ${S_OID_USER}    s_get_range    ${EMPTY}    0:256
                            Run Keyword And Expect Error        *
                            ...  Get Range                      ${NEOFS_IR_WIF}    ${PRIV_CID}    ${S_OID_USER}    s_get_range    ${EMPTY}    0:256
                            Run Keyword And Expect Error        *
                            ...  Get Range                      ${NEOFS_SN_WIF}    ${PRIV_CID}    ${S_OID_USER}    s_get_range    ${EMPTY}    0:256

    # Get Range Hash
                            Get Range Hash                      ${USER_KEY}         ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}    0:256
                            Run Keyword And Expect Error        *
                            ...  Get Range Hash                 ${OTHER_KEY}        ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}    0:256
                            Get Range Hash                      ${NEOFS_IR_WIF}    ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}    0:256
                            Get Range Hash                      ${NEOFS_SN_WIF}    ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}    0:256

    # Search
    @{S_OBJ_PRIV} =	    Create List	                        ${S_OID_USER}       ${S_OID_SYS_SN}
                            Search object                       ${USER_KEY}         ${PRIV_CID}    --root    ${EMPTY}    ${EMPTY}    ${S_OBJ_PRIV}
                            Run Keyword And Expect Error        *
                            ...  Search object                  ${OTHER_KEY}        ${PRIV_CID}    --root    ${EMPTY}    ${EMPTY}    ${S_OBJ_PRIV}
                            Search object                       ${NEOFS_IR_WIF}    ${PRIV_CID}    --root    ${EMPTY}    ${EMPTY}    ${S_OBJ_PRIV}
                            Search object                       ${NEOFS_SN_WIF}    ${PRIV_CID}    --root    ${EMPTY}    ${EMPTY}    ${S_OBJ_PRIV}


    # Head
                            Head object                         ${USER_KEY}         ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}    ${EMPTY}
                            Run Keyword And Expect Error        *
                            ...  Head object                    ${OTHER_KEY}        ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}    ${EMPTY}
                            Head object                         ${NEOFS_IR_WIF}    ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}    ${EMPTY}
                            Head object                         ${NEOFS_SN_WIF}    ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}    ${EMPTY}


    # Delete
                            Run Keyword And Expect Error        *
                            ...  Delete object                  ${OTHER_KEY}        ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}
                            Run Keyword And Expect Error        *
                            ...  Delete object                  ${NEOFS_IR_WIF}    ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}
                            Run Keyword And Expect Error        *
                            ...  Delete object                  ${NEOFS_SN_WIF}    ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}
                            Delete object                       ${USER_KEY}         ${PRIV_CID}    ${S_OID_USER}    ${EMPTY}