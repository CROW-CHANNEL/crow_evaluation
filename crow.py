from bitcoinutils.constants import SATOSHIS_PER_BITCOIN
from bitcoinutils.transactions import Transaction, TxInput, TxOutput
from bitcoinutils.script import Script
from identity import Id
from helper import print_tx
import hashlib
import math


def commitment_script(id_owner: Id, id_other: Id,
                      id_revocation: Id, output_index: int) -> Script:
    if output_index not in (0, 1):
        raise ValueError('A commitment has exactly two outputs')
    revocation_hash = hashlib.sha256(id_revocation.sk.to_bytes()).hexdigest()
    return Script([
        'OP_0' if output_index == 0 else 'OP_1', 'OP_DROP',
        'OP_IF',
            'OP_SHA256', revocation_hash, 'OP_EQUALVERIFY',
            id_other.pk.to_hex(), 'OP_CHECKSIG',
        'OP_ELSE',
            'OP_2', id_owner.pk.to_hex(), id_other.pk.to_hex(),
            'OP_2', 'OP_CHECKMULTISIG',
        'OP_ENDIF',
    ])


def main():
    id_a = Id('2deb49eaa15ad4af3b54601138e9effa646123d2a820dacf2cb2980848fa98e0')
    id_b = Id('2b03c6825c5fffb7af1af7ef8e346ad154d29d1a1409a590be1efd35bac09c68')
    id_channel = Id('a311981dc434789308e3e6e76b56b60e01383f131d5776f0eb179f033677f79e')
    id_revocation_a = Id('9bf936df2650835223f345045a77b7bda2759cefd713ed992d76eab17883a9db')
    id_revocation_b = Id('e2948791eeb82bed30c1980b245446163347273bf6d1db0bfd04490b123dc237')

    tx_input_a = TxInput('cbbdce0e04c86d060d4095956f0998718b8d795a5a9901d5c06eafa7b68fb30b',1)

    tx_input_b = TxInput('cbbdce0e04c86d060d4095956f0998718b8d795a5a9901d5c06eafa7b68fb30b',0)

    money_a = 118_000
    money_b = 79_000
    total = money_a + money_b

    fee = 500                 # Ordinary fee for each example transaction.
    c = 500                   # Extra Punish miner reward, separate from fee.
    v_a = math.floor((total - 2 * c) * 0.4)
    v_b = total - 2 * c - v_a
    delta = 2                 

    ft = get_ft(tx_input_a, tx_input_b, id_a, id_b, id_channel,
                v_a + v_b, c, fee)
    print("CHANNEL_ADDRESS:", id_channel.pk.get_address().to_string())
    print("FUNDING_HEX:", ft.serialize())
    print_tx(ft, 'Funding tx')
    

    state_a = get_state(TxInput(ft.get_wtxid(), 0), id_channel,id_a, id_revocation_a, id_b, v_a, v_b, c, fee)
    print_tx(state_a, 'State tx of A')
    print("STATE_A_HEX:", state_a.serialize())
    state_a_id = state_a.get_wtxid()

    pay_a = get_pay(TxInput(state_a_id, 0), TxInput(state_a_id, 1),
                    id_a, id_b, id_revocation_a, v_a, v_b, c, fee, delta)
    print_tx(pay_a, 'Spend tx of A')
    print("PAY_A_HEX:", pay_a.serialize())

    fast_a = get_fast(TxInput(state_a_id, 0), TxInput(state_a_id, 1),
                      id_a, id_b, id_revocation_a, v_a, v_b, c, fee)
    print_tx(fast_a, 'Fast tx of B on A')

    punish_a = get_punish(TxInput(state_a_id, 0), TxInput(state_a_id, 1),
                          id_a, id_b, id_revocation_a, v_a + v_b, c, fee)
    print_tx(punish_a, 'Punish tx of B on A')
    print("FAST_A_HEX:", fast_a.serialize())
    print("PUNISH_A_HEX:", punish_a.serialize())

    state_b = get_state(TxInput(ft.get_wtxid(), 0), id_channel,
                        id_b, id_revocation_b, id_a, v_b, v_a, c, fee)
    print_tx(state_b, 'State tx of B')
    print("STATE_B_HEX:", state_b.serialize())
    state_b_id = state_b.get_wtxid()

    pay_b = get_pay(TxInput(state_b_id, 0), TxInput(state_b_id, 1),
                    id_b, id_a, id_revocation_b, v_b, v_a, c, fee, delta)
    print_tx(pay_b, 'Spend tx of B')
    print("PAY_B_HEX:", pay_b.serialize())

    fast_b = get_fast(TxInput(state_b_id, 0), TxInput(state_b_id, 1),
                      id_b, id_a, id_revocation_b, v_b, v_a, c, fee)
    print_tx(fast_b, 'Fast tx of A on B')

    punish_b = get_punish(TxInput(state_b_id, 0), TxInput(state_b_id, 1),
                          id_b, id_a, id_revocation_b, v_a + v_b, c, fee)
    print_tx(punish_b, 'Punish tx of A on B')
    print("FAST_B_HEX:", fast_b.serialize())
    print("PUNISH_B_HEX:", punish_b.serialize())

    opt_close = get_close_opt(TxInput(ft.get_wtxid(), 0), id_channel,
                              id_a, id_b, v_a, v_b, c, fee)
    print_tx(opt_close, 'Optimistic close')


def get_ft(input_a: TxInput, input_b: TxInput,
           id_a: Id, id_b: Id, id_channel: Id,
           f: int, c: int, fee: int) -> Transaction:
    tx_out0 = TxOutput(f + 2 * c - fee, id_channel.p2pkh)
    ft = Transaction([input_a, input_b], [tx_out0])
    sig_a = id_a.sk.sign_input(ft, 0, id_a.p2pkh)
    sig_b = id_b.sk.sign_input(ft, 1, id_b.p2pkh)
    input_a.script_sig = Script([sig_a, id_a.pk.to_hex()])
    input_b.script_sig = Script([sig_b, id_b.pk.to_hex()])
    return ft


def get_state(funding: TxInput, id_channel: Id, id_a: Id,
              id_revocation: Id, id_b: Id,
              v_a: int, v_b: int, c: int, fee: int) -> Transaction:
    script0 = commitment_script(id_a, id_b, id_revocation, 0)
    script1 = commitment_script(id_a, id_b, id_revocation, 1)
    tx_out0 = TxOutput(v_a + c - fee, script0.to_p2sh_script_pub_key())
    tx_out1 = TxOutput(v_b + c - fee, script1.to_p2sh_script_pub_key())
    state = Transaction([funding], [tx_out0, tx_out1])
    sig_ft = id_channel.sk.sign_input(state, 0, id_channel.p2pkh)
    funding.script_sig = Script([sig_ft, id_channel.pk.to_hex()])
    return state


def sign_normal(tx: Transaction, id_a: Id, id_b: Id,
                id_revocation: Id) -> Transaction:

    for i, tx_input in enumerate(tx.inputs):
        redeem = commitment_script(id_a, id_b, id_revocation, i)
        sig_a = id_a.sk.sign_input(tx, i, redeem)
        sig_b = id_b.sk.sign_input(tx, i, redeem)
        tx_input.script_sig = Script([
            'OP_0', sig_a, sig_b, 'OP_0', redeem.to_hex()
        ])
    return tx


def get_pay(state1: TxInput, state2: TxInput,
            id_a: Id, id_b: Id, id_revocation: Id,
            v_a: int, v_b: int, c: int, fee: int,
            delta: int = 2) -> Transaction:
    if not (1 <= delta <= 65535):
        raise ValueError('delta must be 1..65535 blocks')
    sequence = delta.to_bytes(4, 'little').hex()
    state1.sequence = sequence if isinstance(state1.sequence, str) else bytes.fromhex(sequence)
    state2.sequence = sequence if isinstance(state2.sequence, str) else bytes.fromhex(sequence)
    tx_out0 = TxOutput(v_a + c - 2 * fee, id_a.p2pkh)
    tx_out1 = TxOutput(v_b + c - fee, id_b.p2pkh)
    pay = Transaction([state1, state2], [tx_out0, tx_out1],
                      version=b'\x02\x00\x00\x00')
    return sign_normal(pay, id_a, id_b, id_revocation)


def get_fast(state1: TxInput, state2: TxInput,
             id_a: Id, id_b: Id, id_revocation: Id,
             v_a: int, v_b: int, c: int, fee: int) -> Transaction:
    tx_out0 = TxOutput(v_a + c - 2 * fee, id_a.p2pkh)
    tx_out1 = TxOutput(v_b + c - fee, id_b.p2pkh)
    fast = Transaction([state1, state2], [tx_out0, tx_out1])
    return sign_normal(fast, id_a, id_b, id_revocation)


def get_punish(state1: TxInput, state2: TxInput,
               id_a: Id, id_b: Id, id_revocation: Id,
               v: int, c: int, fee: int) -> Transaction:
    punish = Transaction([state1, state2],
                         [TxOutput(v + c - 3 * fee, id_b.p2pkh)])
    revocation_preimage = id_revocation.sk.to_bytes().hex()
    for i, tx_input in enumerate(punish.inputs):
        redeem = commitment_script(id_a, id_b, id_revocation, i)
        sig_b = id_b.sk.sign_input(punish, i, redeem)
        tx_input.script_sig = Script([
            sig_b, revocation_preimage, 'OP_1', redeem.to_hex()
        ])
    return punish


def get_close_opt(funding: TxInput, id_channel: Id,
                  id_a: Id, id_b: Id, v_a: int, v_b: int,
                  c: int, fee: int) -> Transaction:
    tx_out0 = TxOutput(v_a + c - fee, id_a.p2pkh)
    tx_out1 = TxOutput(v_b + c - fee, id_b.p2pkh)
    close = Transaction([funding], [tx_out0, tx_out1])
    sig_channel = id_channel.sk.sign_input(close, 0, id_channel.p2pkh)
    funding.script_sig = Script([sig_channel, id_channel.pk.to_hex()])
    return close


if __name__ == '__main__':
    main()
