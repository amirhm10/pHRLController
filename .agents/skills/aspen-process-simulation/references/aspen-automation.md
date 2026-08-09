# Aspen Automation Safety

## Before connection

- verify file and simulation case
- verify Aspen version and interface
- ensure no user-owned active session will be disrupted
- use a copy
- define timeout and cleanup
- define read-only versus write operation

## Read operation

- resolve object path
- verify units and type
- read multiple times if synchronization matters
- compare against GUI or exported value
- log timestamp and case

## Write operation

- validate bounds
- write one variable at a time initially
- read back
- confirm simulator accepted the value
- run only when authorized
- inspect status and messages
- save to a new path

## Failure handling

- do not kill unrelated Aspen processes
- capture error and simulator state
- restore last known safe value
- close only the session owned by the automation
- preserve unsaved user work
