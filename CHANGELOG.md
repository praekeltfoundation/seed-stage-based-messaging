# Changelog

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
