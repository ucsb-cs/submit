from .models import Project, Submission, User


class NoSuchUserException(Exception):
    def __init__(self, message):
        super(NoSuchUserException, self).__init__(message)


class NoSuchProjectException(Exception):
    def __init__(self, message):
        super(NoSuchProjectException, self).__init__(message)


def left_align(text):
    return '<p class="alignleft">{0}</p>'.format(text)


def right_align(text):
    return '<p class="alignright">{0}</p>'.format(text)


def put_in_div(*items):
    return "<div>\n\t{0}\n</div>".format(
        "\n\t".join(items))


def put_in_div_with_alignment(*items):
    params = list(items)
    params.append('<div style="clear: both"></div>')
    return put_in_div(*params)


def link(href, body):
    return '<a href="{0}">{1}</a>'.format(href, body)


class PrevNextUser(object):
    '''Handles the generation of previous and next links
    for users'''

    def __init__(self, request, project, user):
        self._request = request
        self._user = user
        self._project = project
        self._prev_user_pair = self._make_prev_user_pair()
        self._next_user_pair = self._make_next_user_pair()

    def _make_other_user_pair(self, other_user):
        '''Returns a route to a page for the first submission
        for the provided user, or a page showing the user
        has no submissions.  Returns None if the provided
        user is None.  If other_user is not None,
        then you get a pair of (other_user.name, route)'''
        if other_user:
            other_user_submission = \
                Submission.most_recent_submission(self._project.id,
                                                  other_user.id)
            route = None
            if other_user_submission:
                route = self._request.route_path(
                    'submission_item',
                    submission_id=other_user_submission.id)
            else:
                route = self._request.route_path(
                    'project_item_detailed',
                    class_name=self._project.klass.name,
                    username=other_user.username,
                    project_id=self._project.id)
            return (other_user.name, route)

    def _make_prev_user_pair(self):
        return self._make_other_user_pair(
            self._project.prev_user(self._user))

    def _make_next_user_pair(self):
        return self._make_other_user_pair(
            self._project.next_user(self._user))

    def to_html(self):
        return put_in_div_with_alignment(
            self.prev_user_html(),
            self.next_user_html())

    def prev_user_html(self):
        inner = None
        if self._prev_user_pair:
            prev_text = 'Submissions for {0}, the previous user'.format(
                self._prev_user_pair[0])
            inner = link(self._prev_user_pair[1],
                         prev_text)
        else:
            inner = 'There are no users before {0}'.format(self._user.name)
        return left_align(inner)

    def next_user_html(self):
        inner = None
        if self._next_user_pair:
            next_text = 'Submissions for {0}, the next user'.format(
                self._next_user_pair[0])
            inner = link(self._next_user_pair[1],
                         next_text)
        else:
            inner = 'There are no users after {0}'.format(self._user.name)
        return right_align(inner)


class PrevNextSubmission(object):
    '''Handles the generation of previous and next links
    for submissions'''

    def __init__(self, request, submission):
        '''Throws a NoSuchUserException if there is no user behind
        the submission, and a NoSuchProjectException if there
        is no project behind the submission'''
        self._request = request
        self._submission = submission
        self._project = self._make_project()
        self._user = self._make_user()
        self._next_submission = \
            Submission.earlier_submission_for_user(submission)
        self._prev_submission = \
            Submission.later_submission_for_user(submission)
        self._prev_submission = self._make_prev_submission()
        self._next_submission = self._make_next_submission()

    def _make_project(self):
        retval = Project.fetch_by_id(self._submission.project_id)
        if not retval:
            raise NoSuchProjectException(
                "No such project with id {0}".format(
                    self._submission.project_id))
        return retval

    def _make_user(self):
        retval = User.fetch_by_id(self._submission.user_id)
        if not retval:
            raise NoSuchUserException(
                "No such user with id {0}".format(
                    self._submission.user_id))
        return retval

    def _make_prev_submission(self):
        return Submission.later_submission_for_user(self._submission)

    def _make_next_submission(self):
        return Submission.earlier_submission_for_user(self._submission)

    def _submission_route(self, submission):
        if submission:
            return self._request.route_path(
                'submission_item',
                submission_id=submission.id)

    def _prev_submission_route(self):
        return self._submission_route(self._prev_submission)

    def _next_submission_route(self):
        return self._submission_route(self._next_submission)

    def prev_submission_html(self):
        inner = None
        if self._prev_submission:
            inner = '<a href="{0}">Previous submission for {1}</a>'.format(
                self._prev_submission_route(),
                self._user.name)
        else:
            inner = 'No previous submissions for {0}'.format(
                self._user.name)
        return left_align(inner)

    def next_submission_html(self):
        inner = None
        if self._next_submission:
            inner = '<a href="{0}">Next submission for {1}</a>'.format(
                self._next_submission_route(),
                self._user.name)
        else:
            inner = 'No more submissions for {0}'.format(
                self._user.name)
        return right_align(inner)

    def to_html(self):
        return put_in_div_with_alignment(
            self.prev_submission_html(),
            self.next_submission_html())


class PrevNextFull(object):
    '''Generates previous and next buttons for both submissions and users'''
    def __init__(self, request, submission):
        self._sub_prev_next = PrevNextSubmission(request, submission)
        self._users_prev_next = PrevNextUser(request,
                                             self._sub_prev_next._project,
                                             self._sub_prev_next._user)

    def to_html(self):
        return "{0}\n{1}".format(self._sub_prev_next.to_html(),
                                 self._users_prev_next.to_html())
