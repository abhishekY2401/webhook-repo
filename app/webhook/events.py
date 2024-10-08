import pytz
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO,  # Adjust level as needed
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)


class GitHubEvent:

    # initialize github event specific data
    def __init__(self, action_type, repository, sender, timestamp):
        self.action_type = action_type
        self.repository = {
            'id': repository['id'],
            'name': repository['name'],
            'full_name': repository['full_name'],
            'url': repository['html_url']
        }

        self.author = {
            'name': sender['login'],
            'id': sender['id'],
            'avatar_url': sender['avatar_url'],
            'url': sender['html_url']
        }
        self.timestamp = timestamp

        logger.info(f'Created {self.action_type} event for repository {
                    self.repository["full_name"]} by {self.author["name"]} at {self.timestamp}')

    def to_dict(self):

        data = {
            'action-type': self.action_type,
            'repository': self.repository,
            'sender': self.author,
            'timestamp': self.timestamp
        }

        return data


class PushEvent(GitHubEvent):

    # define push event
    def __init__(self, payload):
        action_type = 'PUSH'
        repository = payload['repository']
        sender = payload['sender']
        raw_timestamp = payload['head_commit']['timestamp']

        timestamp = self.convert_to_utc_z_format(raw_timestamp)

        super().__init__(action_type, repository, sender, timestamp)

        self.from_branch = None
        self.request_id = payload['after']
        self.to_branch = payload['ref'].split('/')[-1]

        logger.info(f'PushEvent created with request_id {self.request_id} from branch {
                    self.from_branch} to branch {self.to_branch}')

    def convert_to_utc_z_format(self, timestamp):
        try:
            # Parse the timestamp
            dt = datetime.fromisoformat(timestamp)
            dt_utc = dt.astimezone(pytz.UTC)

            # Return in ISO 8601 format to store in mongo database
            return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        except Exception as e:
            logger.error(f'Error converting timestamp: {e}')
            raise

    def to_dict(self):

        data = {
            'request_id': self.request_id,
            'author': self.author['name'],
            'action-type': self.action_type,
            'from_branch': self.from_branch,
            'to_branch': self.to_branch,
            'timestamp': self.timestamp
        }

        return data


class PullRequestEvent(GitHubEvent):
    def __init__(self, payload):
        print(payload)
        action_type = 'PULL_REQUEST'
        repository = payload['pull_request']['head']['repo']
        owner = payload['pull_request']['user']
        timestamp = payload['pull_request']['created_at']

        super().__init__(action_type, repository, owner, timestamp)

        self.from_branch = payload['pull_request']['head']['ref']
        self.request_id = payload['pull_request']['id']
        self.to_branch = payload['pull_request']['base']['ref']

        self.pull_request = {
            'title': payload['pull_request']['title'],
            'state': payload['pull_request']['state'],
            'merged': payload['pull_request']['merged'],
            'html_url': payload['pull_request']['html_url']
        }
        
        logger.info(f'PullRequestEvent created with request_id {
                    self.request_id} from branch {self.from_branch} to branch {self.to_branch}')


    def to_dict(self):
        data = {
            'request_id': self.request_id,
            'from_branch': self.from_branch,
            'to_branch': self.to_branch,
            'pull_request': self.pull_request,
            'author': self.author['name'],
            'action-type': self.action_type,
            'timestamp': self.timestamp
        }
        return data


class MergeEvent(GitHubEvent):
    def __init__(self, payload):
        action_type = 'MERGE'
        repository = payload['repository']
        owner = payload['pull_request']['user']
        timestamp = payload['pull_request']['merged_at']

        super().__init__(action_type, repository, owner, timestamp)

        self.from_branch = payload['pull_request']['head']['ref']
        self.request_id = payload['pull_request']['merge_commit_sha']
        self.to_branch = payload['pull_request']['base']['ref']

        self.merge_commit = {
            'title': payload['pull_request']['title'],
            'state': payload['pull_request']['state'],
            'merged': payload['pull_request']['merged'],
            'html_url': payload['pull_request']['html_url'],
            'merged_by': payload['pull_request']['merged_by']['login']
        }
        
        logger.info(f'MergeEvent created with request_id {self.request_id} from branch {
                    self.from_branch} to branch {self.to_branch}')


    def to_dict(self):
        data = {
            'request_id': self.request_id,
            'from_branch': self.from_branch,
            'to_branch': self.to_branch,
            'merge_commit': self.merge_commit,
            'author': self.author['name'],
            'action-type': self.action_type,
            'timestamp': self.timestamp
        }
        return data


def create_event(request, payload):
    event_type = request.headers.get('x-github-event')
    logger.debug(f'Creating event for type: {event_type}')

    if event_type == 'push':
        return PushEvent(payload)

    elif event_type == 'pull_request' and payload['action'] == 'opened':
        return PullRequestEvent(payload)

    elif event_type == 'pull_request' and payload['action'] == 'closed':
        return MergeEvent(payload)

    logger.warning(f'Unsupported event type: {event_type}')
    return None
