# Getting Started for Instructors and TAs

To get started you will need an account and a class associated with that
account. While the students must use their umail address to create an account,
instructors and TAs can have accounts created for them. Email Bryce (bboe) with
your full name, CS account email, and the class name. Bryce will create both the
account and the class, add you as an administrator of the class, and trigger the
password reset functionality that will allow you to set a password for the
account, and then login.


## Adding Other Class Administrators

To add other administrators to a class, first ask them for the email with which
they use to login. From the class page, click the "Edit Class Admins" button,
and from that page add them by their email address. All class administrators
share the same privilege.


## Creating / Editing a Project

A project can be created and edited by any of the class administrators for a
class. From the class, page click the "Create new project" button and fill in
the fields as described below (note some of the fields only appear on the edit
page once the project has been created).


### Project Settings

**Name:** the name of the assignment

**Maximum group size:** the total number of students who can group together to
make a single submission.once grouped, all the members of the group can see the
submissions of the other members for that project only (they have to regroup for
each project). Additionally from the TA view, the students appear in a group,
and thus their assignment only needs to be graded once (makes things much
simpler). The instructor or TA can manually join students to make groups larger
than this max for the few one-off cases.

**Deadline:** The deadline visually marks submissions which occur after the
deadline (useful when grading). Additionally, once the deadline has passed, the
submission result delay (see next section) is not applied.

**Results delay:** This is the amount of time between subsequent submissions
that the results are hidden for. The purpose of this field is to prevent
students from "brute forcing" solutions. For example, a student makes a
submission and views the results at 1:00PM. With a submission result delay of 5
minutes, any subsequent submission made between 1:00PM and 1:05PM will have
their results obscured until 5 minutes after the viewing of the last result
page.

**Makefile:** If compilation is required (or other makefile fun) provide a
makefile with various targets. Each testable (described later) can utilize one
of the targets to compile (or run other pre-test code).

**Ready for submission:** check this box when you want students to be able to
submit the assignment. It's a good idea for the TAs to submit their solution
beforehand and verify they receive 100% score and everything works as expected.


### Testable

Each project can have one or more testables. A testable represents a single
executable that needs to be tested. For instance project may require a student
to write a linked list library. One testable could be the "main" program that
the student had to write to show that some functionality of their library works.
Another testable could be a private (not provided to the students) unit-test
type program to allow fine-testing of the student's submitted library.

Each testable has a **name**, and an optional **make target**. The make target
specifies which target in the makefile to run. Regardless if make is run, before
any tests are executed the **executable** file must be available.

Additionally each testable can have one or more **build files**, **execution
files**, and must have at least one **expected file**.

A **build file** is a file that is copied into the environment when the make
target is run. If the students are to implement a specific library, it is
generally a good idea to not allow them to change the header file, and thus all
the header files should be added as a build file. Additionally, if you write any
"private" test code, that should be included as a build file.

An **execution file** is a file that is copied into the present working
directory at the time of program execution. If the program the student wrote
depends on the presence of a dictionary file for instance, then it would need to
be listed, and selected for that testable to make it available.

Finally, an **expected file** is the files that the students are expected to
submit in order for that testable to work.

The selected (make sure to also check the box for the appropriate files for each
testable) **build** and **expected files** will be copied to the environment for
the make process. If the make process produces the file named "executable" then
the tests for that executable will proceed.

The hide results from students option means that students will not see that the
relevant testable even exists. They won't be informed if there are any build
errors, and from their view their score will not include any of the test cases
from that testable. This is useful to have private test cases, though in my
opinion may frustrate students if they think they have 100% and it turns out
they actually do not.


### Test Case

Each testable can have one or more test cases. The following are the parameters
for a test case:

**Name:** simply the name of the test case

**Execution Line:** this is how the program is run (no `./` is needed). If the
tests needs to vary command line arguments, each test case of a testable should
provide different arguments. Note that IO redirection is not supported on this
line (`<` `>` `|`). For advanced usage, python programs, shell scripts, and even
valgrind can be run via the execution line. For example if the student is to
submit a python program foo.py there would be no makefile. However, foo.py would
be listed as an expected file, and would be the executable name. Then an
execution line might look like: `python foo.py arg1 arg2`. Note that only
certain external programs are provided (bash, head, python, python2, python3,
sh, spim, tail, valgrind) but more can be added if needed.

**Points:** the number of points (as an integer) the test case is worth

**Standard Input File:** this file will be used as standard input to the program
when provided. When not provided any read from stdin will result in EOF.

**Output File Source:** Select or name a file with which to capture the output
of the program. If you need to capture multiple streams for the same program
input, then one test case will need to be created for each desired output
stream. If named file is selected and the named file is not produced after
execution then the test case will not be passed, and the result page will
indicate that the expected file was not produced.

**Output File Handling:** This should almost always be `diff`. In the event the
output should be an image, select image and the system will attempt to display
that on the results page. Likewise if text is selected, the system should (it
might not work) simply display the raw results. In both the image and text case,
the student will not receive any points for the test case as it cannot be
determined if the test case passed

**Expected Output File:** when doing a diff, this file is the file that will be
compared against. In order for the test to pass, the students' output must match
the contents of this file exactly (be aware of line ending differences across
systems). By default, the student will be able to see the first three lines of
the diff (note that lines are truncated at a certain length).

**Hide Expected Output:** When this is selected, the student will be able to see
only what their program output (again only the first three lines of the diff)
but not see what was actually expected. Note however, that the results are color
coded, where green means the student added something that shouldn't be in the
output (in this mode there should not be red lines).

