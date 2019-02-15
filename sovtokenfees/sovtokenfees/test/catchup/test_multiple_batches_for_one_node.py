import json

import pytest
from sovtoken.constants import ADDRESS, AMOUNT, TOKEN_LEDGER_ID
from sovtokenfees.constants import FEES

from plenum.common.constants import TXN_TYPE
from sovtokenfees.test.helper import get_amount_from_token_txn, add_fees_request_with_address, \
    get_committed_txns_count_for_pool, nyms_with_fees

from plenum.common.types import f

from plenum.test.delayers import cDelay

from plenum.test.helper import sdk_send_signed_requests, assertExp, sdk_get_and_check_replies

from plenum.test.stasher import delay_rules, delay_rules_without_processing

from stp_core.loop.eventually import eventually

from plenum.common.startable import Mode

from plenum.test.node_catchup.helper import ensure_all_nodes_have_same_data

from plenum.test import waits



@pytest.fixture(scope="module")
def tconf(tconf):
    old_max_size = tconf.Max3PCBatchSize
    tconf.Max3PCBatchSize = 1
    yield tconf

    tconf.Max3PCBatchSize = old_max_size


def test_multiple_batches_for_one_node(looper, helpers,
                                       nodeSetWithIntegratedTokenPlugin,
                                       sdk_pool_handle,
                                       fees_set, address_main, mint_tokens):
    node_set = nodeSetWithIntegratedTokenPlugin
    affected_node = node_set[-1]

    amount = get_amount_from_token_txn(mint_tokens)
    init_seq_no = 1
    request1, request2, request3 = nyms_with_fees(3,
                                                   helpers,
                                                   fees_set,
                                                   address_main,
                                                   amount,
                                                   init_seq_no=init_seq_no)

    expected_txns_length = 2
    txns_count_before = get_committed_txns_count_for_pool(node_set, TOKEN_LEDGER_ID)
    with delay_rules_without_processing(affected_node.nodeIbStasher, cDelay()):
        r1 = sdk_send_signed_requests(sdk_pool_handle, [json.dumps(request1.as_dict)])
        looper.runFor(waits.expectedPrePrepareTime(len(node_set)))
        r2 = sdk_send_signed_requests(sdk_pool_handle, [json.dumps(request2.as_dict)])
        looper.runFor(waits.expectedPrePrepareTime(len(node_set)))
        affected_node.start_catchup()
        looper.run(eventually(lambda: assertExp(affected_node.mode == Mode.participating)))
    txns_count_after = get_committed_txns_count_for_pool(node_set, TOKEN_LEDGER_ID)
    assert txns_count_after - txns_count_before == expected_txns_length
    ensure_all_nodes_have_same_data(looper, node_set)

    r3 = sdk_send_signed_requests(sdk_pool_handle, [json.dumps(request3.as_dict)])
    sdk_get_and_check_replies(looper, r3)
    ensure_all_nodes_have_same_data(looper, node_set)
