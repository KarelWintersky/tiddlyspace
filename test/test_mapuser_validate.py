"""
Test creation of tiddlers in the MAPUSER bag.

The name of the tiddler is the external auth usersign.
The PUT tiddler is empty. A validator sets
fields['mapped_user'] to the current usersign.name.

Note: This does not test the way in which the MAPUSER
information is used by the extractor. Just the proper
creation of the tiddlers.
"""

from test.fixtures import make_test_env

from wsgi_intercept import httplib2_intercept
import wsgi_intercept
import httplib2
import Cookie

from tiddlyweb.store import Store
from tiddlyweb.model.user import User
from tiddlyweb.model.tiddler import Tiddler

from tiddlyweb.web.util import make_cookie

AUTH_COOKIE = None

def setup_module(module):
    make_test_env()
    from tiddlyweb.config import config
    from tiddlyweb.web import serve
    module.secret = config['secret']
    # we have to have a function that returns the callable,
    # Selector just _is_ the callable
    def app_fn():
        return serve.load_app()
    #wsgi_intercept.debuglevel = 1
    httplib2_intercept.install()
    wsgi_intercept.add_wsgi_intercept('0.0.0.0', 8080, app_fn)
    module.store = Store(config['server_store'][0],
            config['server_store'][1], {'tiddlyweb.config': config})
    user = User('cdent')
    user.set_password('cow')
    module.store.put(user)
    user = User('fnd')
    module.store.put(user)


def teardown_module(module):
    import os
    os.chdir('..')


def test_create_map_requires_user():
    http = httplib2.Http()
    response, content = http.request(
            'http://0.0.0.0:8080/bags/MAPUSER/tiddlers/x.auth.thing',
            method='PUT',
            headers={'Content-Type': 'application/json'},
            body='{}')

    assert response['status'] == '403'


def test_create_map_uses_user():
    global AUTH_COOKIE
    http = httplib2.Http()
    response, content = http.request(
            'http://0.0.0.0:8080/challenge/cookie_form',
            body='user=cdent&password=cow',
            method='POST',
            headers={'Content-Type': 'application/x-www-form-urlencoded'})
    assert response.previous['status'] == '303'

    user_cookie = response.previous['set-cookie']
    cookie = Cookie.SimpleCookie()
    cookie.load(user_cookie)
    AUTH_COOKIE = cookie['tiddlyweb_user'].value

    bad_second_cookie = make_cookie('tiddlyweb_secondary_user',
            'x.auth.thing', mac_key='slippy')
    mismatch_second_cookie = make_cookie('tiddlyweb_secondary_user',
            'y.auth.thing', mac_key=secret)
    second_cookie = make_cookie('tiddlyweb_secondary_user',
            'x.auth.thing', mac_key=secret)

# we must have the second cookie
    response, content = http.request(
            'http://0.0.0.0:8080/bags/MAPUSER/tiddlers/x.auth.thing',
            method='PUT',
            headers={'Content-Type': 'application/json',
                'Cookie': 'tiddlyweb_user="%s"' % AUTH_COOKIE},
            body='{"text":"house"}')
    assert response['status'] == '409', content
    assert 'secondary cookie not present' in content

    response, content = http.request(
            'http://0.0.0.0:8080/bags/MAPUSER/tiddlers/x.auth.thing',
            method='PUT',
            headers={'Content-Type': 'application/json',
                'Cookie': 'tiddlyweb_user="%s"; %s' % (
                    AUTH_COOKIE, bad_second_cookie)},
            body='{"text":"house"}')
    assert response['status'] == '409', content
    assert 'secondary cookie invalid' in content

    response, content = http.request(
            'http://0.0.0.0:8080/bags/MAPUSER/tiddlers/x.auth.thing',
            method='PUT',
            headers={'Content-Type': 'application/json',
                'Cookie': 'tiddlyweb_user="%s"; %s' % (
                    AUTH_COOKIE, mismatch_second_cookie)},
            body='{"text":"house"}')
    assert response['status'] == '409', content
    assert 'secondary cookie mismatch' in content

    response, content = http.request(
            'http://0.0.0.0:8080/bags/MAPUSER/tiddlers/x.auth.thing',
            method='PUT',
            headers={'Content-Type': 'application/json',
                'Cookie': 'tiddlyweb_user="%s"; %s' % (
                    AUTH_COOKIE, second_cookie)},
            body='{"text":"house"}')
    assert response['status'] == '204'

    response, content = http.request(
            'http://0.0.0.0:8080/bags/MAPUSER/tiddlers/x.auth.thing',
            method='GET',
            headers={'Accept': 'application/json',
                'Cookie': 'tiddlyweb_user="%s"' % AUTH_COOKIE})
    assert response['status'] == '403'

    tiddler = Tiddler('x.auth.thing', 'MAPUSER')
    tiddler = store.get(tiddler)
    assert tiddler.modifier == 'cdent'
    assert tiddler.text == ''
    assert 'mapped_user' in tiddler.fields
    assert tiddler.fields['mapped_user'] == 'cdent'

    response, content = http.request(
            'http://0.0.0.0:8080/bags/MAPUSER/tiddlers/x.auth.thing',
            method='PUT',
            headers={'Content-Type': 'application/json',
                'Cookie': 'tiddlyweb_user="%s"' % AUTH_COOKIE},
            body='{}')
    assert response['status'] == '403'


def test_user_may_not_map_user():
    """Make user X can't map user Y to themselves."""
    global AUTH_COOKIE
    http = httplib2.Http()
    response, content = http.request(
            'http://0.0.0.0:8080/bags/MAPUSER/tiddlers/fnd',
            method='PUT',
            headers={'Content-Type': 'application/json',
                'Cookie': 'tiddlyweb_user="%s"' % AUTH_COOKIE},
            body='{}')
    assert response['status'] == '409'