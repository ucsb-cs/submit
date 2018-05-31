# Admin Information

If you have access to the server the submission system runs on, then you can
load up the admin terminal by running the shell.sh script. Once in the shell,
you can perform the following tasks:

## Add an Admin User

Any email-based user account can be added as an admin user, however, to prevent
accidental mistakes from being made, it's best to separate the normal account an
instructor uses to manage classes from the "do everything" admin account. Note:
This user will not be able to use the password reset feature as they shouldn't
have a valid email. Password changes should be done in a similar manner.

```Python
s.add(user(name='AdminPhill', username='admin_phill', password='YOUR_PASSWORD', is_admin=True))
t.commit()
```


## Lock Old Classes

One a quarter is over, its classes should be locked to prevent changes and new
submissions. Each quarter should have a unique suffix, e.g., `_w15`, and can be
used to lock all classes with that suffix. Open the shell and run:

```Python
[setattr(x, 'is_locked', True) for x in class_.query_by().filter(class_.name.contains('w15'))]
t.commit()
```


## Unlock a Class

```Python
[setattr(x, 'is_locked', False) for x in class_.query_by().filter(class_.name.contains('CS170_w16'))]
t.commit()
```


## Rename a Class

Classes can be renamed by first selecting the object that represents the class,
and then updating it's attributes. First we must find the class by its current
name:

```Python
tmp = class_.fetch_by(name='CS24_w00')
```

Then we can update the name attribute and commit the changes:

```Python
tmp.name = 'CS24_s01'
tmp.commit()
```


## Unlock a Project

Projects can become locked if the "regenerate expected output" function is run
when the project is not fully configured (no test cases for a testable). First
you must find the project id which can be found in the project's edit url:
https://submit.cs.ucsb.edu/form/project/[project_id]. Open the shell and run:

```Pythonproject.fetch_by_id(project_id).status = 'notready'
t.commit()
```
