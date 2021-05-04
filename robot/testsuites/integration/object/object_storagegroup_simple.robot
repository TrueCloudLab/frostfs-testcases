*** Settings ***
Variables   ../../../variables/common.py

Library     ../${RESOURCES}/neofs.py
Library     ../${RESOURCES}/payment_neogo.py
Library     ../${RESOURCES}/utility_keywords.py
Resource    common_steps_object.robot


*** Test cases ***
NeoFS Simple Storagegroup
    [Documentation]     Testcase to validate NeoFS operations with Storagegroup.
    [Tags]              Object  NeoFS  NeoCLI
    [Timeout]           20 min

    [Setup]             Create Temporary Directory

                        Payment operations
                        Prepare container

    ${FILE_S} =         Generate file of bytes            ${SIMPLE_OBJ_SIZE}
    ${FILE_HASH_S} =    Get file hash                     ${FILE_S}


    # Put two Simple Object
    ${S_OID_1} =        Put object    ${PRIV_KEY}    ${FILE_S}    ${CID}    ${EMPTY}    ${EMPTY}
    ${S_OID_2} =        Put object    ${PRIV_KEY}    ${FILE_S}    ${CID}    ${EMPTY}    ${FILE_USR_HEADER}

    @{S_OBJ_ALL} =	    Create List    ${S_OID_1}    ${S_OID_2}

                        Log    Storage group with 1 object
    ${SG_OID_1} =       Put Storagegroup    ${PRIV_KEY}    ${CID}   ${EMPTY}    ${S_OID_1}
                        List Storagegroup    ${PRIV_KEY}    ${CID}   ${EMPTY}    ${SG_OID_1}
                        Get Storagegroup    ${PRIV_KEY}    ${CID}    ${SG_OID_1}   ${EMPTY}    ${SIMPLE_OBJ_SIZE}    ${S_OID_1}
    ${Tombstone} =      Delete Storagegroup    ${PRIV_KEY}    ${CID}    ${SG_OID_1}    ${EMPTY}
                        Verify Head tombstone    ${PRIV_KEY}    ${CID}    ${Tombstone}    ${SG_OID_1}    ${ADDR}
                        Run Keyword And Expect Error    *
                        ...  Get Storagegroup    ${PRIV_KEY}    ${CID}    ${SG_OID_1}   ${EMPTY}    ${SIMPLE_OBJ_SIZE}    ${S_OID_1}
                        List Storagegroup    ${PRIV_KEY}    ${CID}   ${EMPTY}    @{EMPTY}


                        Log    Storage group with 2 objects
    ${SG_OID_2} =       Put Storagegroup    ${PRIV_KEY}    ${CID}    ${EMPTY}    @{S_OBJ_ALL}
                        List Storagegroup    ${PRIV_KEY}    ${CID}   ${EMPTY}    ${SG_OID_2}
    ${EXPECTED_SIZE} =  Evaluate    2*${SIMPLE_OBJ_SIZE}
                        Get Storagegroup    ${PRIV_KEY}    ${CID}    ${SG_OID_2}   ${EMPTY}    ${EXPECTED_SIZE}    @{S_OBJ_ALL}
    ${Tombstone} =      Delete Storagegroup    ${PRIV_KEY}    ${CID}    ${SG_OID_2}    ${EMPTY}
                        Verify Head tombstone    ${PRIV_KEY}    ${CID}    ${Tombstone}    ${SG_OID_2}    ${ADDR}
                        Run Keyword And Expect Error    *
                        ...  Get Storagegroup    ${PRIV_KEY}    ${CID}    ${SG_OID_2}   ${EMPTY}    ${EXPECTED_SIZE}    @{S_OBJ_ALL}
                        List Storagegroup    ${PRIV_KEY}    ${CID}   ${EMPTY}    @{EMPTY}

                        Log    Incorrect input

                        Run Keyword And Expect Error    *
                        ...  Put Storagegroup    ${PRIV_KEY}    ${CID}    ${EMPTY}    ${UNEXIST_OID}
                        Run Keyword And Expect Error    *
                        ...  Delete Storagegroup    ${PRIV_KEY}    ${CID}    ${UNEXIST_OID}    ${EMPTY}

    [Teardown]          Cleanup

*** Keywords ***

Cleanup
                        Get Docker Logs                     object_storage_group_simple
