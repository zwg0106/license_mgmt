from functools import wraps
from flask import redirect, url_for, g

def login_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        if g.user is not None:
            return func(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return wrapper