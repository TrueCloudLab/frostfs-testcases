*** Settings ***
Variables   common.py

Library     Collections
Library     acl.py
Library     neofs.py
Library     payment_neogo.py

Resource    eacl_tables.robot
Resource    common_steps_acl_bearer.robot
Resource    payment_operations.robot
Resource    setup_teardown.robot

*** Variables ***
&{USER_HEADER} =        key1=1      key2=abc
&{USER_HEADER_DEL} =    key1=del    key2=del
&{ANOTHER_USER_HEADER} =        key1=oth    key2=oth

*** Test cases ***
BearerToken Operations with Filter Requst NotEqual
    [Documentation]         Testcase to validate NeoFS operations with BearerToken with Filter Requst NotEqual.
    [Tags]                  ACL  NeoFSCLI BearerToken
    [Timeout]               20 min

    [Setup]                 Setup

    ${_}    ${_}    ${USER_KEY} =   Prepare Wallet And Deposit

                            Log    Check Bearer token with simple object
    ${FILE_S} =             Generate file    ${SIMPLE_OBJ_SIZE}
                            Check eACL Deny and Allow All Bearer Filter Requst NotEqual    ${USER_KEY}    ${FILE_S}

                            Log    Check Bearer token with complex object
    ${FILE_S} =             Generate file    ${COMPLEX_OBJ_SIZE}
                            Check eACL Deny and Allow All Bearer Filter Requst NotEqual    ${USER_KEY}    ${FILE_S}

    [Teardown]              Teardown    acl_bearer_request_filter_xheader_not_equal


*** Keywords ***

Check eACL Deny and Allow All Bearer Filter Requst NotEqual
    [Arguments]    ${USER_KEY}    ${FILE_S}

    ${CID} =                Create Container Public    ${USER_KEY}
    ${S_OID_USER} =         Put object                 ${USER_KEY}     ${FILE_S}   ${CID}  user_headers=${USER_HEADER}
    ${S_OID_USER_2} =       Put object                 ${USER_KEY}     ${FILE_S}   ${CID}
    ${D_OID_USER} =         Put object                 ${USER_KEY}     ${FILE_S}   ${CID}  user_headers=${USER_HEADER_DEL}
    @{S_OBJ_H} =	        Create List	               ${S_OID_USER}

                            Put object         ${USER_KEY}    ${FILE_S}     ${CID}           user_headers=${ANOTHER_USER_HEADER}
                            Get object         ${USER_KEY}    ${CID}        ${S_OID_USER}    ${EMPTY}      local_file_eacl
                            Search object      ${USER_KEY}    ${CID}        ${EMPTY}         ${EMPTY}      ${USER_HEADER}     ${S_OBJ_H}
                            Head object        ${USER_KEY}    ${CID}        ${S_OID_USER}
                            Get Range          ${USER_KEY}    ${CID}        ${S_OID_USER}    s_get_range       ${EMPTY}      0:256
                            Delete object      ${USER_KEY}    ${CID}        ${D_OID_USER}

                            Set eACL           ${USER_KEY}    ${CID}        ${EACL_DENY_ALL_USER}

                            # The current ACL cache lifetime is 30 sec
                            Sleep    ${NEOFS_CONTRACT_CACHE_TIMEOUT}

    ${filters}=         Create Dictionary    headerType=REQUEST    matchType=STRING_NOT_EQUAL    key=a    value=256
    ${rule1}=           Create Dictionary    Operation=GET             Access=ALLOW    Role=USER    Filters=${filters}
    ${rule2}=           Create Dictionary    Operation=HEAD            Access=ALLOW    Role=USER    Filters=${filters}
    ${rule3}=           Create Dictionary    Operation=PUT             Access=ALLOW    Role=USER    Filters=${filters}
    ${rule4}=           Create Dictionary    Operation=DELETE          Access=ALLOW    Role=USER    Filters=${filters}
    ${rule5}=           Create Dictionary    Operation=SEARCH          Access=ALLOW    Role=USER    Filters=${filters}
    ${rule6}=           Create Dictionary    Operation=GETRANGE        Access=ALLOW    Role=USER    Filters=${filters}
    ${rule7}=           Create Dictionary    Operation=GETRANGEHASH    Access=ALLOW    Role=USER    Filters=${filters}
    ${eACL_gen}=        Create List    ${rule1}    ${rule2}    ${rule3}    ${rule4}    ${rule5}    ${rule6}    ${rule7}
    ${EACL_TOKEN} =     Form BearerToken File      ${USER_KEY}    ${CID}    ${eACL_gen}

                        Run Keyword And Expect Error    *
                        ...  Put object      ${USER_KEY}    ${FILE_S}    ${CID}      user_headers=${USER_HEADER}
                        Run Keyword And Expect Error    *
                        ...  Get object      ${USER_KEY}    ${CID}       ${S_OID_USER}    ${EMPTY}       local_file_eacl
                        #Run Keyword And Expect Error    *
                        #...  Search object  ${USER_KEY}    ${CID}       ${EMPTY}         ${EMPTY}       ${USER_HEADER}    ${S_OBJ_H}
                        Run Keyword And Expect Error    *
                        ...  Head object     ${USER_KEY}    ${CID}       ${S_OID_USER}
                        Run Keyword And Expect Error    *
                        ...  Get Range       ${USER_KEY}    ${CID}       ${S_OID_USER}    s_get_range    ${EMPTY}    0:256
                        Run Keyword And Expect Error    *
                        ...  Delete object   ${USER_KEY}    ${CID}       ${S_OID_USER}

                        Put object       ${USER_KEY}    ${FILE_S}    ${CID}   bearer=${EACL_TOKEN}    user_headers=${USER_HEADER}   options=--xhdr a=2
                        Get object       ${USER_KEY}    ${CID}       ${S_OID_USER}    ${EACL_TOKEN}    local_file_eacl      ${EMPTY}       --xhdr a=2
                        Search object    ${USER_KEY}    ${CID}       ${EMPTY}         ${EACL_TOKEN}    ${USER_HEADER}   ${EMPTY}       --xhdr a=2
                        Head object      ${USER_KEY}    ${CID}       ${S_OID_USER}    bearer_token=${EACL_TOKEN}    options=--xhdr a=2
                        Get Range        ${USER_KEY}    ${CID}       ${S_OID_USER}    s_get_range      ${EACL_TOKEN}    0:256          --xhdr a=2
                        Get Range Hash   ${USER_KEY}    ${CID}       ${S_OID_USER}    ${EACL_TOKEN}    0:256            --xhdr a=2
                        Delete object    ${USER_KEY}    ${CID}       ${S_OID_USER}    bearer=${EACL_TOKEN}    options=--xhdr a=2
