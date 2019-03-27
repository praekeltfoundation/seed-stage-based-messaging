# Changelog

## 0.12.1 (2019-03-27)
### Enhancements
1. Added metadata field for messages in contentstore
   ([#136](https://github.com/praekelt/seed-stage-based-messaging/pull/135))

## 0.12.0 (2019-02-15)
### Enhancements
1. Reduced the amount of database requests for subscription processing
   ([#135](https://github.com/praekelt/seed-stage-based-messaging/pull/135))

## 0.11.7 (2019-01-14)
### Enhancements
1. Added python black and isort auto formatting
   ([#133](https://github.com/praekelt/seed-stage-based-messaging/pull/133))
1. Added prometheus metrics endpoint
   ([#134](https://github.com/praekelt/seed-stage-based-messaging/pull/134))

## 0.11.6 (2018-12-14)
### Fixes
1. Fix the number of messages behind calculation for behind subscriptions
   monitoring and management task.
   ([#132](https://github.com/praekelt/seed-stage-based-messaging/pull/132))
## 0.11.5 (2018-12-07)
### Fixes
1. Add soft_time_limit to send sub tasks and auto retry for SoftTimeLimitExceeded

## 0.11.4 (2018-12-06)
### Fixes
1. Move the find_behind_subscriptions task to the highmemory queue

## 0.11.3 (2018-12-05)
### Fixes
1. Adding send subtasks to the correct queues.

## 0.11.2 (2018-12-05)
### Fixes
1. Move the send message task into separate tasks for acks_late

### Enhancements
 - Monitor subscriptions that are behind.

## 0.11.1 (2018-11-13)
### Fixes
1. Fix flake8 check on testsettings.py

## 0.11.0 (2018-11-13)
### Fixes
1. Upgrade to Django 2.1 and update all other requirements
   ([#121](https://github.com/praekelt/seed-stage-based-messaging/pull/121))
1. Upgrade requests to fix security vulnerability

## 0.10.1 (2018-10-18)
### Enhancements
1. Send images with text messages
   ([#119](https://github.com/praekeltfoundation/seed-stage-based-messaging/pull/119))
1. Add human-readable labels for message sets
   ([#120](https://github.com/praekeltfoundation/seed-stage-based-messaging/pull/120))

## 0.10.0 (2018-06-05)
### Enhancements
 - Changed to having a schedule per schedule, instead of a schedule per
   subscription. Any new or updated schedules will automatically be created or
   updated in the scheduler, but for existing schedules, there's a
   `sync_schedules` management command. Existing schedules linking directly
   to subscriptions will be cancelled whenever they get called.
 - Added a new celery queue, 'highmemory', which has the task to queue up all
   the subscription sends for each schedule when the endpoint is called
