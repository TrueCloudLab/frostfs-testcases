*** Settings ***
Variables   common.py

Library     neofs_verbs.py
Library     neofs.py
Library     payment_neogo.py
Library     contract_keywords.py
Library     Collections

Resource    common_steps_object.robot
Resource    setup_teardown.robot
Resource    payment_operations.robot

*** Variables ***
${CLEANUP_TIMEOUT} =    10s
&{FILE_USR_HEADER} =        key1=1      key2=abc
&{FILE_USR_HEADER_OTH} =    key1=2


*** Test cases ***
NeoFS Complex Object Operations
    [Documentation]     Testcase to validate NeoFS operations with complex object.
    [Tags]              Object
    [Timeout]           20 min

    [Setup]             Setup

    ${WALLET}   ${ADDR}     ${WIF} =   Prepare Wallet And Deposit
    ${CID} =            Prepare container       ${WIF}

    ${FILE} =           Generate file of bytes              ${COMPLEX_OBJ_SIZE}
    ${FILE_HASH} =      Get file hash                       ${FILE}

    ${S_OID} =          Put object                 ${WIF}    ${FILE}       ${CID}
    ${H_OID} =          Put object                 ${WIF}    ${FILE}       ${CID}        user_headers=${FILE_USR_HEADER}
    ${H_OID_OTH} =      Put object                 ${WIF}    ${FILE}       ${CID}        user_headers=${FILE_USR_HEADER_OTH}

    Should Be True     '${S_OID}'!='${H_OID}' and '${H_OID}'!='${H_OID_OTH}'

                        Validate storage policy for object  ${WIF}    2             ${CID}         ${S_OID}
                        Validate storage policy for object  ${WIF}    2             ${CID}         ${H_OID}
                        Validate storage policy for object  ${WIF}    2             ${CID}         ${H_OID_OTH}

    @{S_OBJ_ALL} =      Create List    ${S_OID}       ${H_OID}     ${H_OID_OTH}
    @{S_OBJ_H} =        Create List    ${H_OID}
    @{S_OBJ_H_OTH} =    Create List    ${H_OID_OTH}

                        Search Object    ${WIF}    ${CID}        --root       expected_objects_list=${S_OBJ_ALL}

    ${GET_OBJ_S} =      Get object               ${WIF}    ${CID}        ${S_OID}
    ${GET_OBJ_H} =      Get object               ${WIF}    ${CID}        ${H_OID}

    ${FILE_HASH_S} =    Get file hash            ${GET_OBJ_S}
    ${FILE_HASH_H} =    Get file hash            ${GET_OBJ_H}

                        Should Be Equal          ${FILE_HASH_S}   ${FILE_HASH}
                        Should Be Equal          ${FILE_HASH_H}   ${FILE_HASH}

                        Get Range Hash           ${WIF}    ${CID}        ${S_OID}          ${EMPTY}       0:10
                        Get Range Hash           ${WIF}    ${CID}        ${H_OID}          ${EMPTY}       0:10

                        Get Range                ${WIF}    ${CID}        ${S_OID}          s_get_range    ${EMPTY}       0:10
                        Get Range                ${WIF}    ${CID}        ${H_OID}          h_get_range    ${EMPTY}       0:10

                        Search object            ${WIF}    ${CID}        --root        expected_objects_list=${S_OBJ_ALL}
                        Search object            ${WIF}    ${CID}        --root        filters=${FILE_USR_HEADER}      expected_objects_list=${S_OBJ_H}
                        Search object            ${WIF}    ${CID}        --root        filters=${FILE_USR_HEADER_OTH}  expected_objects_list=${S_OBJ_H_OTH}

                        Head object              ${WIF}    ${CID}        ${S_OID}
    &{RESPONSE} =       Head object              ${WIF}    ${CID}        ${H_OID}
                        Dictionary Should Contain Sub Dictionary
                            ...     ${RESPONSE}[header][attributes]
                            ...     ${FILE_USR_HEADER}
                            ...     msg="There are no User Headers in HEAD response"

                        Verify Split Chain       ${WIF}    ${CID}        ${S_OID}
                        Verify Split Chain       ${WIF}    ${CID}        ${H_OID}

    ${TOMBSTONE_S} =    Delete object            ${WIF}    ${CID}        ${S_OID}
    ${TOMBSTONE_H} =    Delete object            ${WIF}    ${CID}        ${H_OID}

                        Verify Head tombstone    ${WIF}    ${CID}        ${TOMBSTONE_S}     ${S_OID}    ${ADDR}
                        Verify Head tombstone    ${WIF}    ${CID}        ${TOMBSTONE_H}     ${H_OID}    ${ADDR}

                        Tick Epoch
                        # we assume that during this time objects must be deleted
                        Sleep   ${CLEANUP_TIMEOUT}

                        Run Keyword And Expect Error        "rpc error: status: code = 1024 message = object already removed"
                        ...  Get object          ${WIF}    ${CID}        ${S_OID}           ${EMPTY}       ${GET_OBJ_S}
                        Run Keyword And Expect Error        "rpc error: status: code = 1024 message = object already removed"
                        ...  Get object          ${WIF}    ${CID}        ${H_OID}           ${EMPTY}       ${GET_OBJ_H}

    [Teardown]          Teardown    object_complex
