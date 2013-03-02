from tempfile import NamedTemporaryFile
from zipfile import ZipFile
from .models import File, Project, SubmissionToFile, User


class ZipSubmission(object):
    """Puts a submission into a zip file.

    This packages up the following:
    -Makefile to build the project
    -User-submitted code that can be build with said makefile
    -Test cases, along with any stdin needed to run said test cases

    """
    def __init__(self, submission, request):
        self.submission = submission
        self.request = request
        self.dirname = '{0}_{1}'.format(submission.user.username,
                                        submission.id)
        self.backing_file = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, tpe, value, traceback):
        self.close()

    def _add_makefile(self):
        self.write(self.file_path(self.submission.project.makefile),
                   'Makefile')

    def _add_user_code(self):
        filemapping = SubmissionToFile.fetch_file_mapping_for_submission(
            self.submission.id)
        for filename, db_file in filemapping.iteritems():
            self.write(self.file_path(db_file), filename)

    def actual_filename(self):
        return self.backing_file.name

    def close(self):
        self.backing_file.close()
        self.backing_file = None

    def open(self):
        self.backing_file = NamedTemporaryFile()
        try:
            self.zip = ZipFile(self.backing_file, 'w')
            self._add_makefile()
            self._add_user_code()
        finally:
            self.zip.close()

    def file_path(self, file_):
        return File.file_path(self.request.registry.settings['file_directory'],
                              file_.sha1)

    def pretty_filename(self):
        return '{0}.zip'.format(self.dirname)

    def write(self, backing_file, archive_filename):
        '''Writes the given file to the archive with the given name.
        Puts everything in the same directory as specified by
        get_dirname_from_submission'''
        self.zip.write(backing_file,
                       "{0}/{1}".format(self.dirname, archive_filename))
