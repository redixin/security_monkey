#     Copyright 2014 Netflix, Inc.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.

from security_monkey.views import AuthenticatedService
from security_monkey.views import ACCOUNT_FIELDS
from security_monkey.datastore import Account
from security_monkey.datastore import User
from security_monkey.account_manager import get_account_by_id
from security_monkey import db, rbac

from flask import request
from flask_restful import marshal, reqparse
import json

class AccountGetPutDelete(AuthenticatedService):
    decorators = [
        rbac.allow(["View"], ["GET"]),
        rbac.allow(["Admin"], ["PUT", "DELETE"])
    ]
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        super(AccountGetPutDelete, self).__init__()

    def get(self, account_id):
        """
            .. http:get:: /api/1/account/<int:id>

            Get a list of Accounts matching the given criteria

            **Example Request**:

            .. sourcecode:: http

                GET /api/1/account/1 HTTP/1.1
                Host: example.com
                Accept: application/json, text/javascript

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                {
                    third_party: false,
                    name: "example_name",
                    notes: null,
                    identifier: "111111111111",
                    active: true,
                    id: 1,
                    account_type: "AWS",
                    auth: {
                        authenticated: true,
                        user: "user@example.com"
                    }
                }

            :statuscode 200: no error
            :statuscode 401: Authentication failure. Please login.
        """

        result = get_account_by_id(account_id)

        account_marshaled = marshal(result.__dict__, ACCOUNT_FIELDS)
        account_marshaled = dict(
            account_marshaled.items() +
            {'account_type': result.account_type.name}.items()
        )

        custom_fields_marshaled = []
        for field in result.custom_fields:
            field_marshaled = {
                                  'name': field.name,
                                  'value': field.value,
                              }
            custom_fields_marshaled.append(field_marshaled)
        account_marshaled['custom_fields'] = custom_fields_marshaled

        account_marshaled['auth'] = self.auth_dict
        return account_marshaled, 200

    def put(self, account_id):
        """
            .. http:put:: /api/1/account/1

            Edit an existing account.

            **Example Request**:

            .. sourcecode:: http

                PUT /api/1/account/1 HTTP/1.1
                Host: example.com
                Accept: application/json

                {
                    'name': 'edited_account'
                    'identifier': '0123456789',
                    'notes': 'this account is for ...',
                    'active': true,
                    'third_party': false
                }

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                {
                    'name': 'edited_account'
                    'identifier': '0123456789',
                    'notes': 'this account is for ...',
                    'active': true,
                    'third_party': false
                    'account_type': 'AWS'
                }

            :statuscode 200: no error
            :statuscode 401: Authentication Error. Please Login.
        """

        args = json.loads(request.json)
        account_type = args['account_type']
        name = args['name']
        identifier = args['identifier']
        notes = args['notes']
        active = args['active']
        third_party = args['third_party']
        account_id = args['id']
        custom_fields = args['custom_fields']

        from security_monkey.account_manager import account_registry
        account_manager = account_registry.get(account_type)()
        account = account_manager.update(account_id, account_type, name, active,
                    third_party, notes, identifier, custom_fields=custom_fields)

        if not account:
            return {'status': 'error. Account ID not found.'}, 404

        marshaled_account = marshal(account.__dict__, ACCOUNT_FIELDS)
        marshaled_account['auth'] = self.auth_dict

        return marshaled_account, 200

    def delete(self, account_id):
        """
            .. http:delete:: /api/1/account/1

            Delete an account.

            **Example Request**:

            .. sourcecode:: http

                DELETE /api/1/account/1 HTTP/1.1
                Host: example.com
                Accept: application/json

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 202 Accepted
                Vary: Accept
                Content-Type: application/json

                {
                    'status': 'deleted'
                }

            :statuscode 202: accepted
            :statuscode 401: Authentication Error. Please Login.
        """

        # Need to unsubscribe any users first:
        users = User.query.filter(User.accounts.any(Account.id == account_id)).all()
        for user in users:
            user.accounts = [account for account in user.accounts if not account.id == account_id]
            db.session.add(user)
        db.session.commit()

        account = Account.query.filter(Account.id == account_id).first()

        db.session.delete(account)
        db.session.commit()

        return {'status': 'deleted'}, 202


class AccountPostList(AuthenticatedService):
    decorators = [
        rbac.allow(["View"], ["GET"]),
        rbac.allow(["Admin"], ["POST"])
    ]

    def __init__(self):
        super(AccountPostList, self).__init__()
        self.reqparse = reqparse.RequestParser()

    def post(self):
        """
            .. http:post:: /api/1/account/

            Create a new account.

            **Example Request**:

            .. sourcecode:: http

                POST /api/1/account/ HTTP/1.1
                Host: example.com
                Accept: application/json

                {
                    'name': 'new_account'
                    'identifier': '0123456789',
                    'notes': 'this account is for ...',
                    'active': true,
                    'third_party': false
                    'account_type': 'AWS'
                }

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 201 Created
                Vary: Accept
                Content-Type: application/json

                {
                    'name': 'new_account'
                    'identifier': '0123456789',
                    'notes': 'this account is for ...',
                    'active': true,
                    'third_party': false
                    'account_type': 'AWS'
                    ''
                }

            :statuscode 201: created
            :statuscode 401: Authentication Error. Please Login.
        """

        args = request.json
        account_type = args['account_type']
        name = args['name']
        identifier = args['identifier']
        notes = args['notes']
        active = args['active']
        third_party = args['third_party']
        custom_fields = args['custom_fields']

        from security_monkey.account_manager import account_registry
        account_manager = account_registry.get(account_type)()
        account = account_manager.create(account_type, name, active, third_party,
                    notes, identifier, custom_fields=custom_fields)

        marshaled_account = marshal(account.__dict__, ACCOUNT_FIELDS)
        marshaled_account['auth'] = self.auth_dict
        return marshaled_account, 200

    def get(self):
        """
            .. http:get:: /api/1/accounts

            Get a list of Accounts matching the given criteria

            **Example Request**:

            .. sourcecode:: http

                GET /api/1/accounts HTTP/1.1
                Host: example.com
                Accept: application/json, text/javascript

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                {
                    count: 1,
                    items: [
                        {
                            third_party: false,
                            name: "example_name",
                            notes: null,
                            role_name: null,
                            identifier: "111111111111",
                            active: true,
                            id: 1,
                            s3_name: "example_name"
                        },
                    ],
                    total: 1,
                    page: 1,
                    auth: {
                        authenticated: true,
                        user: "user@example.com"
                    }
                }

            :statuscode 200: no error
            :statuscode 401: Authentication failure. Please login.
        """

        self.reqparse.add_argument('count', type=int, default=30, location='args')
        self.reqparse.add_argument('page', type=int, default=1, location='args')

        args = self.reqparse.parse_args()
        page = args.pop('page', None)
        count = args.pop('count', None)

        result = Account.query.order_by(Account.id).paginate(page, count, error_out=False)

        items = []
        for account in result.items:
            account_marshaled = marshal(account.__dict__, ACCOUNT_FIELDS)
            account_marshaled = dict(
                account_marshaled.items() +
                {'account_type': account.account_type.name}.items()
            )

            items.append(account_marshaled)

        marshaled_dict = {
            'total': result.total,
            'count': len(items),
            'page': result.page,
            'items': items,
            'auth': self.auth_dict
        }

        return marshaled_dict, 200
