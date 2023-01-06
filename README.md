# Team Roles Geekbot Sweep

A Slack/Geekbot/Google Calendar App to sweep through 2i2c team members, assign Team Roles, and track them in our Team Roles calendar

[![codecov](https://codecov.io/gh/2i2c-org/team-roles-geekbot-sweep/branch/main/graph/badge.svg?token=411D82WZOS)](https://codecov.io/gh/2i2c-org/team-roles-geekbot-sweep)

## Summary

This repository is a collection of Python code that tracks which 2i2c team members are currently serving in our Team Roles (Meeting Facilitator and Support Steward).
The code works out which team member is due to take over a given role, and dynamically generates Geekbot standups in Slack to visibly and explicitly notify the given team member that they are due to take over the role.
It also creates events in the Team Roles Google Calendar to make the role changes more visible.

:fire: **The Meeting Facilitator role has been retired.
While the code still remains in this repository, it is no longer actively run as part of CI/CD.** :fire:

### Useful Documentation

**API docs:**

- [Slack API](https://api.slack.com/methods)
- [Geekbot API](https://geekbot.com/developers/)
- [Google Calendar API](https://developers.google.com/calendar/api)

**Tutorials:**

- [How to Build Your First Slack Bot with Python](https://www.fullstackpython.com/blog/build-first-slack-bot-python.html)
- [Building a simple bot using Python in 10 minutes](https://github.com/slackapi/python-slack-sdk/tree/main/tutorial)
- [Quickstart Guide to the Google Calendar API with Python](https://developers.google.com/calendar/api/quickstart/python)

## Getting setup

### Package Installation

Installing the dependencies requires [`poetry`](https://python-poetry.org/).
You can install the dependencies by running:

```bash
poetry install
```

### Setting up `sops` for secret decryption

Secrets required to execute the code in this repository are stored in the `secrets` folder and are encrypted with [`sops`](https://github.com/mozilla/sops).
You will therefore need to have `sops` installed to run this code locally.
See [this guide](https://infrastructure.2i2c.org/en/latest/tutorials/setup.html#step-3-authenticate-with-google-cloud-to-decrypt-our-secret-files) to setup `sops` before executing any code here.

## Team Roles JSON file structure

Which 2i2c teams members are serving (or have served) in a given role are stored in the `team-roles.json` file, which has the below structure.

We keep track of both a team member's Slack display name and user ID.
This is because interacting with the Slack and Geekbot APIs requires the user ID, but it is more human-readable to also have the names.

For the Support Steward, we track both the current and incoming team members as we have two people overlapping in this role.

We have an extra role here called `standup_manager`.
This is the team member who created `GEEKBOT_API_KEY` and will be added to all standups.
This is because Geekbot only provides personal API keys and these keys do not have permission to see any standups the owner of said key is not a member of.
:fire: **If you are changing this role, you will need to recreate `GEEKBOT_API_KEY`.** :fire:

```json
{
    "standup_manager": {
      "name": "display_name",
      "id": "slack_id"
    },
    "meeting_facilitator": {
        "name": "display_name",
        "id": "slack_id"
    },
    "support_steward": {
        "incoming": {
            "name": "display_name",
            "id": "slack_id"
        },
        "current": {
            "name": "display_name",
            "id": "slack_id"
        }
    }
}
```

## Scripts

All scripts are written in Python and are located in the [`src`](src/) folder.

### `get_slack_usergroup_members.py`

This script interacts with the Slack API to produce a dictionary of Slack users who are members of a given Slack usergroup and their IDs.
The script requires the `usergroup_name` variable to be set, which is the name of the Slack usergroup to list members of, e.g., `meeting-facilitators` or `support-stewards`.

The script will generate a dictionary of members of `usergroup_name` where the keys are the users' display names, and the values are their associated user IDs.
The dictionary is ordered alphabetically by its keys.

**Command line usage:**

Running the following command will print the dictionary of team members' names and IDs to the console.

```bash
poetry run list-members
```

**Help info:**

```bash
usage: list-members [-h] usergroup_name

List the members and IDs of a Slack usergroup

positional arguments:
  usergroup_name  The name of the Slack usergroup to list members of

optional arguments:
  -h, --help      show this help message and exit
```

### `update_team_roles.py`

This script generates the next team member to serve in a given role by iterating one place through the appropriate Slack usergroup (either `meeting-facilitators` or `support-stewards`).
It depends on [`get_slack_usergroup_members.py`](#get_slack_usergroup_memberspy) to pull the list of usergroup members from Slack.
The desired usergroup to pull the members of is parsed to the script via the `USERGROUP_NAME` environment variable.

The team member _currently_ serving in the role is pulled from the current event in the Team Roles calendar.
If no event is found, the current team member is read from the `team-roles.json` file.
The updated team roles are written back to the same file.
There are command line options to determine which role is to be updated.

**Command line usage:**

To execute, run the following command:

```bash
poetry run update-team-role { meeting-facilitator | support-steward }
```

**Help info:**

```bash
usage: update-team-role [-h] {meeting-facilitator,support-steward}

Update our Team Roles by iterating through 2i2c team members

positional arguments:
  {meeting-facilitator,support-steward}
                        The role to update

optional arguments:
  -h, --help            show this help message and exit
```

### `create_geekbot_standup.py`

This script reads in [`team-roles.json`](#team-roles-json-file-structure) after it has been modified by [`update_team_roles.py`](#update_team_rolespy) and generates a Geekbot standup to notify the incoming team member for their upcoming role.

The `MeetingFacilitatorStandup` broadcasts to the `team-updates` Slack channel, and the `SupportStewardStandup` broadcasts to the `support-freshdesk` channel.
The [Geekbot app](https://geekbot.com/) needs to be installed to the Slack workspace and invited to the channels to which it will broadcast.
Command line options are provided to select which role a standup should be created for.

**Command line usage:**

To execute, run the following command:

```bash
poetry run create-standup { meeting-facilitator | support-steward }
```

**Help info:**

```bash
usage: create-standup [-h] {meeting-facilitator,support-steward}

Create Geekbot standup apps to manage the transition of Team Roles through 2i2c team members

positional arguments:
  {meeting-facilitator,support-steward}
                        The role to create a Geekbot Standup to transition

optional arguments:
  -h, --help            show this help message and exit
```

### `set_current_roles.py`

This script is used to initialise the `team-roles.json` file with manual input.
It depends upon [`get_slack_usergroup_members.py`](#get_slack_usergroup_memberspy) to convert Slack display names into user IDs.

This script requires the following environment variables to be set:

- `USERGROUP_NAMES`: The name of the Slack usergroup to list members of, e.g., `meeting-facilitators` or `support-stewards`.
  Multiple usergroups can be provided by separating them with a comma.
- `CURRENT_SUPPORT_STEWARD`: The Slack display name of the team member currently serving in the Support Steward role (i.e. for more than two weeks)
- `INCOMING_SUPPORT_STEWARD`: The Slack display name of the team member most recently taking up service in the Support Steward role (i.e. for less than two weeks)
- `STANDUP_MANAGER`: This is the Slack display name of the team member who created `geekbot_api_token.json` and will be added to all standups.
  This role is required since Geekbot only offers personal API keys and the script won't be able to see any exisitng standups that the owner of the key is not a member of.
  :fire: **If you are changing this role, you will need to recreate `geekbot_api_token.json`.** :fire:

This script is paired with the [`populate-current-roles` workflow](#populate-current-rolesyaml) to commit the updated `team-roles.json` file to the repo for future CI/CD runs of the bot.

**Note:** You can additionally provide the following environment variable, but it is no longer required since the Meeting Facilitator role is now retired:

- `CURRENT_MEETING_FACILITATOR`: The Slack display name of the team member currently serving in the Meeting Facilitator role

**Command line usage:**

To execute this script, run:

```bash
poetry run populate-current-roles
```

### `create_events_rolling_update.py`

This script is used to create the next event for a Team Role given that a series of events already exist in a Google Calendar.
It calculates the required metadata for the new event from the last event available on the calendar.
It depends upon [`get_slack_usergroup_members.py`](#get_slack_usergroup_memberspy) to get an ordered list of the team members who fulfil these roles.
The desired usergroup is parsed to the script via the `USERGROUP_NAME` environment variable.

**Command line usage:**

To execute this script, run:

```bash
poetry run create-next-event { meeting-facilitator | support-steward }
```

**Help info:**

```bash
usage: create-next-event [-h] {meeting-facilitator,support-steward}

Create the next event in a series for a Team Role in a Google Calendar

positional arguments:
  {meeting-facilitator,support-steward}
                        The role to create an event for

optional arguments:
  -h, --help            show this help message and exit
```

### `create_events_bulk.py`

This script is used to generate a large number of events for a Team Role in a Google Calendar in bulk.
It begins generating events either from the day the script is executed or from a provided reference date.
It depends upon [`get_slack_usergroup_members.py`](#get_slack_usergroup_memberspy) to get an ordered list of the team members who fulfil these roles.
The desired usergroup is parsed to the script via the `USERGROUP_NAME` environment variable.

#### :fire: Reference Dates for the Support Steward :fire:

Our Support Steward role starts and ends on Wednesdays for a period of 4 weeks with a team member rotating on/off the role every two weeks.

The `create_events_bulk.py` script accounts for this by adjusting the reference date to the next Wednesday in the calendar.
However, the next Wednesday might not necessarily line up with the 2/4 weekly cycle of the Support Steward.
So take caution when running this script and choose a reference date carefully before executing.

The two `create_events_*.py` scripts can't delete events and so, if they are repeatedly run, will create duplicate events.
See [`delete_events_bulk.py`](#delete_events_bulkpy) for information on deleting events from the calendar.

**Command line usage:**

To execute this script, run:

```bash
poetry run create-bulk-events { meeting-facilitator | support-steward }
```

**Help info:**

```bash
usage: create-bulk-events [-h] [-n N_EVENTS] [-d DATE] [-m TEAM_MEMBER] {meeting-facilitator,support-steward}

Bulk create a series of Team Role events in a Google Calendar

positional arguments:
  {meeting-facilitator,support-steward}
                        The role to create events for

options:
  -h, --help            show this help message and exit
  -n N_EVENTS, --n-events N_EVENTS
                        The number of role events to create. Defaults to 12 for Meeting Facilitator and 26 for Support Steward (both 1 year's worth).
  -d DATE, --date DATE  A reference date to begin creating events from. Defaults to appending events from the last in the series, or TODAY if no events exist. WARNING: EXPERIMENTAL
                        FEATURE. This flag is MUTUALLY INCLUSIVE with --team-member [-m].
  -m TEAM_MEMBER, --team-member TEAM_MEMBER
                        The name of the team member currently serving in the role. Defaults to being pulled from either the last calendar event, or team-roles.json if a calendar event
                        doesn't not exist. This flag is MUTUALLY INCLUSIVE with --date [-d].
```

### `delete_events_bulk.py`

This script is used to delete all upcoming events in the calendar for a role from a reference date.
We may wish to run this script when a team member has been onboarded/off-boarded from a role and we need to update the calendar en masse.
And so we can clear the upcoming events with this script, and regenerate events with [`create_events_bulk.py`](#create_events_bulkpy).

A date from which to select events for deletion can be provided, and events whose start date is _after_ this reference date will be retrieved.
For instance, if you run the program on 2022-09-15, events that have start dates after that date will be retrieved.

**Command line usage:**

```bash
poetry run delete-bulk-events { meeting-facilitator | support-steward }
```

**Help info:**

```bash
usage: delete-bulk-events [-h] [-d DATE] {meeting-facilitator,support-steward}

Bulk delete all upcoming Team Role events in a Google Calendar

positional arguments:
  {meeting-facilitator,support-steward}
                        The role to delete events for

options:
  -h, --help            show this help message and exit
  -d DATE, --date DATE  A reference date to begin creating events from. Defaults to TODAY.
```

### `gcal_api_auth.py`

This script is a helper script that returns an authenticated instance of the Google Calendar API for the [`create_events_rolling_update.py`](#create_events_rolling_updatepy) and [`create_events_bulk.py`](#create_events_bulkpy) to create events in a Google Calendar.

### `event_handling.py`

This script is a helper script that centralises logic around generating metadata for events, creating them, and deleting them from a Google Calendar.

### `sops.py`

This is a helper script that securely decrypts secrets using `sops` into a temporary file for use throughout the package.

## CI/CD workflows

All our CI/CD workflows are powered by [GitHub Actions](https://docs.github.com/en/actions) and the configuration is located in the [`.github/workflows`](.github/workflows/) folder.

### `populate-current-roles.yaml`

This workflow runs the [`set_current_roles.py` script](#set_current_rolespy) to generate an initial `team-roles.json` file and commit it to the repo for use in future GitHub Actions workflow runs.
It can be triggered manually and requires the environment variables required by `set_current_roles.py` and [`get_slack_usergroup_members.py`](#get_slack_usergroup_memberspy) to be provided as inputs.

### `meeting-facilitator.yaml`

:fire: **The Meeting Facilitator role has been retired and, even though the workflow file still exists, it has been [manually disabled](https://docs.github.com/en/actions/managing-workflow-runs/disabling-and-enabling-a-workflow#disabling-a-workflow).
If we wish to bring back the Meeting Facilitator role, we can [enable the workflow](https://docs.github.com/en/actions/managing-workflow-runs/disabling-and-enabling-a-workflow#enabling-a-workflow) again.** :fire:

This workflow file contains two jobs: `create-standup` and `update-calendar`.
It is scheduled to run at midnight UTC on the 28th of each month and can also be triggered manually using workflow dispatch.

The `create-standup` job runs the [`create_geekbot_standup.py`](#create_geekbot_standuppy) script to update the Meeting Facilitator role in the `team-roles.json` file and create/update a Geekbot Standup App to notify the new team member serving in the role.
When manually triggered, updating the team roles file is optional, for example if you'd just like to reset the Geekbot App.
The Geekbot App is configured to notify the next Meeting Facilitator on the first Monday of each month.

The `update-calendar` job runs the [`create_events_rolling_update.py`](#create_events_rolling_updatepy) script to create the next event in the series, keeping the calendar populated roughly one year in advance.
If running manually, this job can be skipped completely.

### `support-steward.yaml`

This workflow file contains three jobs: `is-two-weeks`, `create-standup` and `update-calendar`.
It is scheduled to run at midnight UTC weekly on Mondays and can also be manually triggered using workflow dispatch.

The `is-two-weeks` job determines if we are on a two-week cycle since a defined reference date.
This is because we transfer the Support Steward role every two weeks, but writing a cronjob for every two weeks is tough!
The Geekbot App is configured to notify the next Support Steward on every other Wednesday.
If we are not on a two-week cycle the following jobs will not be triggered, unless specified to run using workflow dispatch inputs.

The `create-standup` job runs the [`create_geekbot_standup.py`](#create_geekbot_standuppy) to update the Support Steward role in the `team-roles.json` file and create/update a Geekbot Standup App to notify the new team member serving in the role.
When manually triggered, updating the team roles file is optional, for example if you'd just like to reset the Geekbot App.

The `update-calendar` job runs the [`create_events_rolling_update.py`](#create_events_rolling_updatepy) script to create the next event in the series, keeping the calendar populated roughly one year in advance.
If running manually, this job can be skipped completely.

## Regarding secrets

The following secrets with stated permissions are stored in the `secrets` folder.

- `calendar_id.json`: The ID of a Google Calendar to which a GCP Service Account has permission to manage events
- `gcp_service_account.json`: A Google Cloud Service Account Key with permissions to access Google's Calendar API
- `geekbot_api_token.json`: A personal API token from the `STANDUP_MANAGER`'s account to authenticate against the Geekbot API
- `slack_bot_token.json`: A bot user token for a Slack App installed into the workspace.
  The bot requires the `usergroups:read` and `users:read` permission scopes to operate.
  It does not need to be a member of any channels in the Slack workspace.
