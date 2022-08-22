# Team Roles Geekbot Sweep

A Slack/Geekbot/Google Calendar App to sweep through 2i2c team members, assign Team Roles, and track them in our Team Roles calendar

## Summary

This repository is a collection of Python code that tracks which 2i2c team members are currently serving in our Team Roles (Meeting Facilitator and Support Steward).
The code works out which team member is due to take over a given role, and dynamically generates Geekbot standups in Slack to visibly and explicitly notify the given team member that they are due to take over the role.
It also creates events in the Team Roles Google Calendar to make the role changes more visible.

### Useful Documentation

**API docs:**

- [Slack API](https://api.slack.com/methods)
- [Geekbot API](https://geekbot.com/developers/)
- [Google Calendar API](https://developers.google.com/calendar/api)

**Tutorials:**

- [How to Build Your First Slack Bot with Python](https://www.fullstackpython.com/blog/build-first-slack-bot-python.html)
- [Building a simple bot using Python in 10 minutes](https://github.com/slackapi/python-slack-sdk/tree/main/tutorial)
- [Quickstart Guide to the Google Calendar API with Python](https://developers.google.com/calendar/api/quickstart/python)

## Installation

Installing the dependencies requires [`poetry`](https://python-poetry.org/).
You can install the dependencies by running:

```bash
poetry install
```

## Team Roles JSON file structure

Which 2i2c teams members are serving (or have served) in a given role are stored in the `team-roles.json` file, which has the below structure.

We keep track of both a team members Slack display name and user ID.
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

### `get_slack_team_members.py`

This script interacts with the Slack API to produce a dictionary of Slack users who are members of a given Slack team (formally called a "usergroup" in the API), and their IDs.
The script requires two variables to be set:

- `team_name` (cli argument): The name of the Slack team to list members of, e.g., `meeting-facilitators` or `support-stewards`
- `SLACK_BOT_TOKEN` (environment variable): A bot user token for a Slack App installed into the workspace.
  The bot requires the `usergroups:read` and `users:read` permission scopes to operate.
  It does not need to be a member of any channels in the Slack workspace.

The script will generate a dictionary of members of `TEAM_NAME` where the keys are the users' display names, and the values are their associated user IDs.
The dictionary is ordered alphabetically by its keys.

**Command line usage:**

Running the following command will print the dictionary of team members' names and IDs to the console.

```bash
poetry run list-team-members
```

**Help info:**

```bash
usage: list-team-members [-h] team_name

List the members and IDs of a Slack usergroup

positional arguments:
  team_name   The name of the Slack usergroup to list members of

optional arguments:
  -h, --help  show this help message and exit
```

### `update_team_roles.py`

This script generates the next team member to serve in a given role by iterating one place through the appropriate Slack team (either `meeting-facilitators` or `support-stewards`).
It depends on [`get_slack_team_members.py`](#get_slack_team_memberspy) to pull the list of team members from Slack and therefore needs those environment variables set (Note: `team_name` is promoted to an environment variable for this script).
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

The script requires the `GEEKBOT_API_KEY` environment variable to be set with a valid API key for communicating with Geekbot's API.
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
It depends upon [`get_slack_team_members.py`](#get_slack_team_memberspy) to convert Slack display names into user IDs.

In addition to the two environment variables required by `get_slack_team_members.py`, this script also requires the following environment variables to be set:

- `CURRENT_MEETING_FACILITATOR`: The Slack display name of the team member currently serving in the Meeting Facilitator role
- `CURRENT_SUPPORT_STEWARD`: The Slack display name of the team member currently serving in the Support Steward role (i.e. for more than two weeks)
- `INCOMING_SUPPORT_STEWARD`: The Slack display name of the team member most recently taking up service in the Support Steward role (i.e. for less than two weeks)
- `STANDUP_MANAGER`: This is the Slack display name of the team member who created `GEEKBOT_API_KEY` and will be added to all standups.
  This role is required since Geekbot only offers personal API keys and the script won't be able to see any exisitng standups that the owner of the key is not a member of.
  :fire: **If you are changing this role, you will need to recreate `GEEKBOT_API_KEY`.** :fire:

This script is paired with the [`populate-current-roles` workflow](#populate-current-rolesyaml) to commit the updated `team-roles.json` file to the repo for future CI/CD runs of the bot.

**Command line usage:**

To execute this script, run:

```bash
poetry run populate-current-roles
```

### `create_events_rolling_update.py`

This script is used to create the next event for a Team Role given that a series of events already exist in a Google Calendar.
It calculates the required metadata for the new event from the last event available on the calendar.
It depends upon [`get_slack_team_members.py`](#get_slack_team_memberspy) to get an ordered list of the team members who fulfil these roles.

In addition to the two environment variables required be `get_slack_team_members.py` (Note: `team_name` has been promoted to an environment variable for this script), this script also requires the following environment variables to be set:

- `GCP_SERVICE_ACCOUNT_KEY`: A Google Cloud Service Account with permissions to access Google's Calendar API
- `CALENDAR_ID`: The ID of a Google Calendar to which the above Service Account has permission to manage events

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
It depends upon [`get_slack_team_members.py`](#get_slack_team_memberspy) to get an ordered list of the team members who fulfil these roles.

In addition to the two environment variables required be `get_slack_team_members.py` (Note: `team_name` has been promoted to an environment variable for this script), this script also requires the following environment variables to be set:

- `GCP_SERVICE_ACCOUNT_KEY`: A Google Cloud Service Account with permissions to access Google's Calendar API
- `CALENDAR_ID`: The ID of a Google Calendar to which the above Service Account has permission to manage events

#### :fire: Reference Dates for the Support Steward :fire:

Our Support Steward role starts and ends on Wednesdays for a period of 4 weeks with a team member rotating on/off the role every two weeks.

The `create_events_bulk.py` script accounts for this by adjusting the reference date to the next Wednesday in the calendar.
However, the next Wednesday might not necessarily line up with the 2/4 weekly cycle of the Support Steward.
So take caution when running this script and choose a reference date carefully before executing.

The two `create_events_*.py` scripts can't delete events and so, if they are repeatedly run, will create duplicate events.

**Command line usage:**

To execute this script, run:

```bash
poetry run create-bulk-events { meeting-facilitator | support-steward }
```

**Help info:**

```bash
usage: create-bulk-events [-h] [-m TEAM_MEMBER] [-n N_EVENTS] [-d DATE] {meeting-facilitator,support-steward}

Bulk create a series of Team Role events in a Google Calendar

positional arguments:
  {meeting-facilitator,support-steward}
                        The role to create events for

optional arguments:
  -h, --help            show this help message and exit
  -m TEAM_MEMBER, --team-member TEAM_MEMBER
                        The name of the team member currently serving in the role. Will be pulled from team-roles.json if not provided.
  -n N_EVENTS, --n-events N_EVENTS
                        The number of role events to create. Defaults to 12 for Meeting Facilitator and 26 for Support Steward (both 1 year's worth).
  -d DATE, --date DATE  A reference date to begin creating events from. Defaults to today. WARNING: EXPERIMENTAL FEATURE.
```

### `gcal_api_auth.py`

This script is a helper script that returns an authenticated instance of the Google Calendar API for the [`create_events_rolling_update.py`](#create_events_rolling_updatepy) and [`create_events_bulk.py`](#create_events_bulkpy) to create events in a Google Calendar.

## CI/CD workflows

All our CI/CD workflows are powered by [GitHub Actions](https://docs.github.com/en/actions) and the configuration is located in the [`.github/workflows`](.github/workflows/) folder.

### `populate-current-roles.yaml`

This workflow runs the [`set_current_roles.py` script](#set_current_rolespy) to generate an initial `team-roles.json` file and commit it to the repo for use in future GitHub Actions workflow runs.
It can be triggered manually and requires the environment variables required by `set_current_roles.py` and [`get_slack_team_members.py`](#get_slack_team_memberspy) to be provided as inputs.
Note that `SLACK_BOT_TOKEN` is provided via a GitHub Action Environment Secret.

### `meeting-facilitator.yaml`

This workflow file contains two jobs: `create-standup` and `update-calendar`.
It is scheduled to run at midnight UTC on the 28th of each month.

The `create-standup` job runs the [`create_geekbot_standup.py`](#create_geekbot_standuppy) script to update the Meeting Facilitator role in the `team-roles.json` file and create/update a Geekbot Standup App to notify the new team member serving in the role.
It can be manually triggered with the option of updating the team roles file or not, for example if you'd just like to reset the Geekbot App.
The Geekbot App is configured to notify the next Meeting Facilitator on the first Monday of each month.

The `update-calendar` job runs the [`create_events_rolling_update.py`](#create_events_rolling_updatepy) script to create the next event in the series, keeping the calendar populated roughly one year in advance.
This job cannot be manually triggered.

### `support-steward.yaml`

This workflow file contains three jobs: `is-two-weeks`, `create-standup` and `update-calendar`.
It is scheduled to run at midnight UTC weekly on Mondays.

The `is-two-weeks` job determines if we are on a two-week cycle since a defined reference date.
This is because we transfer the Support Steward role every two weeks, but writing a cronjob for every two weeks is tough!
The Geekbot App is configured to notify the next Support Steward on every other Wednesday.
If we are not on a two-week cycle, the following jobs will not be triggered.

The `create-standup` job runs the [`create_geekbot_standup.py`](#create_geekbot_standuppy) to update the Support Steward role in the `team-roles.json` file and create/update a Geekbot Standup App to notify the new team member serving in the role.
It can be manually triggered with the option of updating the team roles file or not, for example if you'd just like to reset the Geekbot App.

The `update-calendar` job runs the [`create_events_rolling_update.py`](#create_events_rolling_updatepy) script to create the next event in the series, keeping the calendar populated roughly one year in advance.
This job cannot be manually triggered.
