#!/usr/bin/env python
from flask import Flask, request, render_template, redirect, url_for, jsonify
from flask import make_response
from flask import session as login_session

import psycopg2
import json, string, random

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import requests

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']


app = Flask(__name__, static_url_path='/static')
app.secret_key = "pns07bL1ON6AC6BqHT6Pe5OG"
app.config['SESSION_TYPE'] = 'filesystem'

### Main functions
@app.route('/')
def showRoot():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
        for x in xrange(32))

    # loggedInStatus = True
    # print loggedInStatus
    if 'username' not in login_session:
        loggedInStatus = False
        login_session['state'] = ''
        login_session['email'] = ''
        login_session['state'] = ''
        login_session['gplus_id'] = ''
        login_session['access_token'] = ''
        access_token = ""
    else:
        loggedInStatus = True
        access_token = login_session['access_token']

    login_session['state'] = state

    return render_template('index.html', STATE=state, login_session=login_session, access_token=access_token, loggedInStatus=loggedInStatus)


@app.route('/clear')
def makeClear():
    del login_session['access_token']
    del login_session['user_id']
    del login_session['gplus_id']
    del login_session['username']
    del login_session['email']
    del login_session['picture']

    print login_session
    return "Okay"


### Actually complex GLogin
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Obtain authorization code
    code = request.data

    # print request.args.get('state')
    # print login_session['state']
    print request
    print "The code is: "
    print code

    try:
        # Upgrade the authorization code into a credentials object

        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'

        credentials = oauth_flow.step2_exchange(code)

        print "Inside"
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        print "Here"
        return response

    print "1234"


    # Check that the access token is valid.
    access_token = credentials.access_token

    print access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    loggedInStatus = True
    print "ACCESS TOKEN"
    print access_token

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')

    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id


    # # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    print "I made it"
    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    # output = ''
    # output += 'Logged in:  '
    output = login_session['username']
    # output += ''
    # output += '<img src="'
    # output += login_session['picture']
    # output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    # flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# DISCONNECT - Revoke a current user's token and reset their login_session
@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        # return response
        loggedInStatus = False
        return redirect('/')
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    print access_token
    print result

    if result['status'] == '200':
        # Reset the user's sesson.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        # return response
        print "ABC 123"
        loggedInStatus = False
        # return render_template('index.html', loggedInStatus=loggedInStatus)
        return redirect('/')
    else:
        # For whatever reason, the given token was invalid.
        # del login_session

        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


def createUser(login_session):
    # newUser = User(name=login_session['username'], email=login_session[
    #                'email'], picture=login_session['picture'])
    # session.add(newUser)
    # session.commit()
    # user = session.query(User).filter_by(email=login_session['email']).one()
    # return user.id
    return login_session['email']


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def isLoggedIn():
    return "Hello"
    # if 'username' not in login_session:
    #     return False
# loggedInStatus = True
    #     return True


## Main subroutine
if __name__ == '__main__':
    # isLoggedIn = isLoggedIn()
    loggedInStatus = False
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
