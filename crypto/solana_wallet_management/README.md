| Action in `chat_proto.py`        | Calls function in `solana_service.py` | Compatible? |
|----------------------------------|---------------------------------------|:-----------:|
| "balance"                        | get_balance_from_address              |     ✅      |
| "transactions"/"history"         | get_recent_transactions               |     ✅      |
| "tokens"                         | get_token_balances                    |     ✅      |
| "info"/"account"                 | get_account_info                      |     ✅      |