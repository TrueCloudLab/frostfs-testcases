*** Settings ***
Variables   common.py

Library     acl.py
Library     container.py
Library     neofs_verbs.py
Library     utility_keywords.py

Resource    eacl_tables.robot
Resource    common_steps_acl_bearer.robot
Resource    payment_operations.robot

*** Test cases ***
BearerToken Operations for Inaccessible Container
    [Documentation]         Testcase to validate NeoFS operations with BearerToken for Inaccessible Container.
    [Tags]                  ACL   BearerToken
    [Timeout]               20 min


    ${WALLET}   ${_}     ${_} =   Prepare Wallet And Deposit

                            Log    Check Bearer token with simple object
    ${FILE_S}    ${_} =     Generate file    ${SIMPLE_OBJ_SIZE}
                            Check Container Inaccessible and Allow All Bearer    ${WALLET}    ${FILE_S}

                            Log    Check Bearer token with complex object
    ${FILE_S}    ${_} =     Generate file    ${COMPLEX_OBJ_SIZE}
                            Check Container Inaccessible and Allow All Bearer    ${WALLET}    ${FILE_S}


*** Keywords ***

Check Container Inaccessible and Allow All Bearer
    [Arguments]    ${WALLET}    ${FILE_S}

                # 0x40000000 is inaccessible ACL
    ${CID} =    Create Container           ${WALLET}    basic_acl=0x40000000
                Prepare eACL Role rules    ${CID}

                Run Keyword And Expect Error        *
                ...  Put object        ${WALLET}    ${FILE_S}     ${CID}    user_headers=${FILE_USR_HEADER}
                Run Keyword And Expect Error        *
                ...  Get object        ${WALLET}    ${CID}        ${S_OID_USER}    ${EMPTY}       local_file_eacl
                Run Keyword And Expect Error        *
                ...  Search object     ${WALLET}    ${CID}        ${EMPTY}         ${EMPTY}       ${FILE_USR_HEADER}
                Run Keyword And Expect Error        *
                ...  Head object       ${WALLET}    ${CID}        ${S_OID_USER}
                Run Keyword And Expect Error        *
                ...  Get Range         ${WALLET}    ${CID}        ${S_OID_USER}    0:256
                Run Keyword And Expect Error        *
                ...  Delete object     ${WALLET}    ${CID}        ${S_OID_USER}

    ${rule1} =          Create Dictionary       Operation=PUT           Access=ALLOW    Role=USER
    ${rule2} =          Create Dictionary       Operation=SEARCH        Access=ALLOW    Role=USER
    ${eACL_gen} =       Create List             ${rule1}    ${rule2}

    ${EACL_TOKEN} =     Form BearerToken File       ${WALLET}    ${CID}   ${eACL_gen}

                Run Keyword And Expect Error        *
                ...  Put object        ${WALLET}    ${FILE_S}     ${CID}       ${EACL_TOKEN}       user_headers=${FILE_USR_HEADER}
                Run Keyword And Expect Error        *
                ...  Search object     ${WALLET}    ${CID}        ${EMPTY}     ${EACL_TOKEN}       ${FILE_USR_HEADER}