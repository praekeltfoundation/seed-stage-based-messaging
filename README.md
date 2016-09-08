# seed-staged-based-messaging
Seed Stage-Based Messaging Store

## Apps & Models:
  * contentstore
    * Schedule
    * MessageSet
    * BinaryContent
    * Message
  * subscriptions
    * Subscription

## Metrics
##### subscriptions.created.sum
`sum` Total number of subscriptions created

##### subscriptions.send_next_message_errored.sum
`sum` Total number of subscriptions that broke on send_next_message task

##### subscriptions.total.last
`last` Total number of subscriptions created

##### subscriptions.active.last
`last` Total number of active subscriptions

##### subscriptions.broken.last
`last` Total number of broken subscriptions

##### subscriptions.completed.last
`last` Total number of completed subscriptions

##### subscriptions.<messageset_shortname>.active.last
`last` Total number of active subscriptions for each messageset
