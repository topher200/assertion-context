import re

import flask
import flask_login
import redis
import simplejson
from flask_oauthlib.client import OAuth
from simplekv.decorator import PrefixDecorator
from simplekv.memory.redisstore import RedisStore


persistent_storage = RedisStore(redis.StrictRedis(host='redis'))
USER_DB = PrefixDecorator('user_', persistent_storage)


class User(flask_login.UserMixin):
    def __init__(self, email, oauth_access_token):
        self.__email = email
        self.__oauth_access_token = oauth_access_token

    def get_id(self):
        return self.__email

    @property
    def is_authenticated(self):
        """
            User is authorized if their email matches our configured regex
        """
        regex = flask.current_app.config['AUTHORIZED_EMAIL_REGEX']
        return re.search(regex, self.__email) is not None

    @property
    def email(self):
        return self.__email

    @property
    def oauth_access_token(self):
        return self.__oauth_access_token

    def document(self):
        """
            Returns the document form of this object for db storage

            Document form is a dictionary of <field name>: <value> pairs.
        """
        return {
            "email": self.__email,
            "oauth_access_token": self.__oauth_access_token,
        }

    def __repr__(self):
        return str(self.document())

    @staticmethod
    def generate_from_document(document):
        """
            Restores an instance of this object from the dictionary output from document()
        """
        assert isinstance(document, dict), (type(document), document)
        return User(
            document['email'],
            document['oauth_access_token'],
        )


def add_login_handling(app):
    """
        Takes a flask app. Adds our OAuth based authenticator to it

        All frontend APIs require login. The /login endpoint forwards to google's OAuth2 flow.
        Authorized users' oauth is saved to the local USER_DB. flask_login handles confirming that
        the user is logged in and saving a persistent client-side token to remember login status
        between sessions.
    """
    login_manager = flask_login.LoginManager()

    # oauth setup
    oauth = OAuth()
    GOOGLE_OAUTH = oauth.remote_app(
        'google',
        request_token_params={
            'scope': 'email',
            'state': 'skdfjsdkjfsdkfsdjkf'
        },
        base_url='https://www.googleapis.com/oauth2/v1/',
        request_token_url=None,
        access_token_method='POST',
        access_token_url='https://accounts.google.com/o/oauth2/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        consumer_key=app.config['OAUTH_CLIENT_ID'],
        consumer_secret=app.config['OAUTH_CLIENT_SECRET'],
    )

    @login_manager.user_loader
    def load_user(email):  # pylint: disable=unused-variable
        try:
            document = simplejson.loads(USER_DB.get(email))
        except KeyError:
            return None
        return User.generate_from_document(document)

    @app.route('/login')
    @login_manager.unauthorized_handler
    def login():  # pylint: disable=unused-variable
        response = GOOGLE_OAUTH.authorize(callback=flask.url_for('authorized', _external=True))
        return response

    @app.route('/logout')
    def logout():  # pylint: disable=unused-variable
        USER_DB.delete(flask_login.current_user.email)
        flask_login.logout_user()
        return flask.redirect(flask.url_for('index'))

    @app.route('/login/authorized')
    def authorized():  # pylint: disable=unused-variable
        resp = GOOGLE_OAUTH.authorized_response()
        if resp is None:
            return 'Access denied: reason=%s error=%s' % (
                flask.request.args['error_reason'],
                flask.request.args['error_description']
            )
        # we save a temp token, get user information, then delete it and save the real user
        flask.session['temp_oauth_token'] = (resp['access_token'], '')
        me = GOOGLE_OAUTH.get('userinfo')
        flask.session.pop('temp_oauth_token')

        # create the user
        user = User(me.data['email'], (resp['access_token'], ''))
        flask_login.login_user(user, remember=True)
        USER_DB.put(user.email, simplejson.dumps(user.document()))
        return flask.redirect(flask.url_for('index'))

    @GOOGLE_OAUTH.tokengetter
    def get_google_oauth_token():  # pylint: disable=unused-variable
        """ Returns the oauth token for a logged in user. Returns None if we're not logged in"""
        # if we're in the user signin flow, return their temp token
        if 'temp_oauth_token' in flask.session:
            return flask.session.get('temp_oauth_token')

        # normal path - return the auth'd user token
        if flask_login.current_user and flask_login.current_user.is_authenticated:
            return flask_login.current_user.oauth_access_token
        return None

    login_manager.init_app(app)
