#Server↔Server Protocol
Why: Needed for presence, routing, and gossip in a decentralized overlay network.

Bootstrap:

1.When a new server joins, it sends SERVER_HELLO_JOIN to an introducer.
2.The introducer responds with SERVER_WELCOME (list of peers).
3.The new server then announces itself to others with SERVER_ANNOUNCE.

Presence Gossip:

1.On user connect → broadcast USER_ADVERTISE.
2.On user disconnect → broadcast USER_REMOVE.
3.Other servers update user_locations and re-gossip.

Forwarded Delivery:

1.If recipient is local → deliver via USER_DELIVER.
2.If recipient is on another server → forward via PEER_DELIVER.
3.Duplicates suppressed using LRU (seen_ids).

Health:

1.Heartbeat every 15s.
2.If no heartbeat from a peer in 45s → connection dropped.

#User↔Server Protocol

Why: Defines how clients (users) connect to servers.

USER_HELLO:

1.User sends HELLO with UUIDv4.
2.If already taken, server replies ERROR: NAME_IN_USE.
3.Otherwise, server registers user locally and gossips their presence.

Direct Messages (DM):

1.Client encrypts with RSA-OAEP + signs with PSS.
2.Server does NOT decrypt — just forwards to the correct destination via routing.

Public Channel:

1.Public chat messages (MSG_PUBLIC_CHANNEL) are fanned out to all users and servers.
2.Group key management can be extended (per SOCP spec).

File Transfer:

1.Three phases: FILE_START, FILE_CHUNK, FILE_END.
2.Server routes file chunks like messages.
3.Order/size constraints must be enforced at client side.

ACKs & ERRORs:
1.Server already sends ERROR messages if:

Invalid signature
Unknown message type
Duplicate username
ACKs are optional.