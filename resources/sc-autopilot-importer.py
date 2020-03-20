# /*
#  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  * SPDX-License-Identifier: MIT-0
#  *
#  * Permission is hereby granted, free of charge, to any person obtaining a copy of this
#  * software and associated documentation files (the "Software"), to deal in the Software
#  * without restriction, including without limitation the rights to use, copy, modify,
#  * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#  * permit persons to whom the Software is furnished to do so.
#  *
#  * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#  * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
#  * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#  * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#  * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#  */
#NOTE: This code does not consider paginated calls, please modify to handle paginations for all API calls

#!/usr/bin/env python
from __future__ import print_function
__version__ = '1.0'
__author__ = '@SagarKhasnis@'
__email__ = 'khasnis@'
import boto3
import botocore
import random
import time
import sys
import argparse
import os
import urllib
import json
from botocore.vendored import requests

'''Auto import of shared SC portfolios, and setting up of local portfolio with IAM principals and constraints
'''

def setup_portfolios(sc_iam_role,launch_constraint,share_type):
    print("Looking for shared portfolios in this account...")
    sc_client = boto3.client('servicecatalog')
    try:
        #List portfolio shares
        shared_portfolios = sc_client.list_accepted_portfolio_shares(PortfolioShareType=share_type)
        print("The portfolio share type is {} ".format(share_type))
        print("The following portfolios are shared with this account: {}".format(shared_portfolios['PortfolioDetails']))

        #Look for local copy of shared portfolio. If not, create one.
        local_portfolios = sc_client.list_portfolios()
        shared_port_details = ''
        for shared_port in shared_portfolios['PortfolioDetails']:
            exists = False
            shared_port_details = sc_client.describe_portfolio(Id=shared_port['Id'])
            for local_port in local_portfolios['PortfolioDetails']:
                if(local_port['DisplayName'] == shared_port['DisplayName']):
                    exists = True
                    print("Portfolio {} exists, will not be created!".format(shared_port['DisplayName']))
                    #associate iam to portfolio
                    associate_iam_principal(local_port,sc_iam_role,sc_client)
                    #logic to copy products and associate with local portfolio
                    copy_products_to_local_account(local_port,shared_port,launch_constraint,sc_client)

            #if a local copy of portfolio does not exist, create a local portfolio
            if(exists==False):
                response = sc_client.create_portfolio(
                    AcceptLanguage='en',
                    DisplayName=shared_port.get('DisplayName', ''),
                    Description=shared_port.get('Description', ''),
                    ProviderName=shared_port.get('ProviderName', ''),
                    Tags=[
                        {
                            'Key': 'PortfolioType',
                            'Value': 'Inherited'
                        },
                    ]
                )
                print("Created local portfolio successfully. Response: {}".format(response))
                associate_iam_principal(response['PortfolioDetail'], sc_iam_role,sc_client)
                copy_products_to_local_account(response['PortfolioDetail'],shared_port,launch_constraint,sc_client)
        return "Success"
    except botocore.exceptions.ClientError as e:
        print(e)
        print("Failed In the Create PortfolioShare for. Error : {}".format(e))
        sys.exit(1)
    return "Success"

def associate_iam_principal(local_portfolio, sc_iam_role,sc_client):
    print("Assigning IAM entity to portfolio {}...".format(local_portfolio['DisplayName']))
    try:
        #Associating IAM principal with portfolio
        iam_response = sc_client.associate_principal_with_portfolio(PortfolioId=local_portfolio['Id'],
                                                                    PrincipalARN=sc_iam_role,
                                                                    PrincipalType='IAM'
                                                                    )
    except botocore.exceptions.ClientError as e:
        print(e)
        print("Failed In the associate IAM principal for portfolio. Response: {} Error : {}".format(iam_response,e))
        sys.exit(1)
    return "Success"

def copy_products_to_local_account(local_port,shared_port,launch_constraint,sc_client):
    print("Copying products to local account for portfolio {}...".format(local_port['DisplayName']))
    try:
        print("Copying shared products to local account...")
        #Get list of products in portfolio and copy them if they don't exist
        shared_products = sc_client.search_products_as_admin(PortfolioId= shared_port['Id'])
        print("List of products shared with this account... {}".format(shared_products['ProductViewDetails']))
        #Get a list of products pre-existing in the account
        local_products = sc_client.search_products_as_admin()
        #Compare existing products with shared products
        for y in shared_products['ProductViewDetails']:
            exists = False
            for x in local_products['ProductViewDetails']:
                if(x['ProductViewSummary']['Name'] == y['ProductViewSummary']['Name']):
                    exists = True
                    print("Product {} exists, will not be copied!".format(y['ProductViewSummary']['Name']))
                    associate_products_to_local_portfolio(x['ProductViewSummary']['Name'],local_port,launch_constraint,sc_client)
           #if shared product does not exist in current account, then copy
            if(exists==False):
                response = sc_client.copy_product(
                    AcceptLanguage='en',
                    SourceProductArn=y['ProductARN'],
                    CopyOptions=['CopyTags',]
                )
                print("Copied product {} to account successfully. Response: {}".format(y['ProductARN'],response))
                time.sleep(20)
                associate_products_to_local_portfolio(y['ProductViewSummary']['Name'],local_port,launch_constraint,sc_client)

    except botocore.exceptions.ClientError as e:
        print(e)
        print("Failed In the Create PortfolioShare for. Error : {}".format(e))
        sys.exit(1)
    return "Success"

def associate_products_to_local_portfolio(product_name,local_port,launch_constraint,sc_client):
    print("Associating local products to local portfolio {}...".format(local_port['DisplayName']))
    try:
        print("Associating product {} to portfolio {}...".format(product_name,local_port['DisplayName']))
        product_id = ''
        local_products = sc_client.search_products_as_admin()
        #find product ID of the product name provided
        for x in local_products['ProductViewDetails']:
            if(x['ProductViewSummary']['Name'] == product_name):
                product_id = x['ProductViewSummary']['ProductId']
                print("Product ID found-{}".format(product_id))
        #associating product with local portfolio
        associate_resp = sc_client.associate_product_with_portfolio(
            AcceptLanguage='en',
            ProductId = product_id,
            PortfolioId =local_port['Id'],
        )
        print("Product {} associated with portfolio {}. Response: {}".format(product_name,local_port['DisplayName'],associate_resp))
        create_constraint(product_id,local_port,launch_constraint,sc_client)
    except botocore.exceptions.ClientError as e:
        print(e)
        print("Could not associate product to local portfolio. Error : {}".format(e))
        sys.exit(1)
    return "Success"

def create_constraint(product_id,local_port,launch_constraint,sc_client):
    print("Creating constraints for product {} to local account for portfolio {}...".format(product_id,local_port['DisplayName']))
    try:
        #check if product has constraints already, if yes skip
        exists = False
        constraint_check = sc_client.list_constraints_for_portfolio(PortfolioId=local_port['Id'],ProductId=product_id)
        for constraint in constraint_check['ConstraintDetails']:
            if(constraint['Type']=='LAUNCH'):
                exists = True
                print("{} constraint exists for this product {} ".format(constraint['Type'],product_id))
        #create constraints for product
        if(exists==False):
            constraint_response = sc_client.create_constraint(
                PortfolioId=local_port['Id'],
                ProductId= product_id,
                Parameters= launch_constraint,
                Type='LAUNCH',
                Description= 'Launch constraint for product ID ' + str(product_id)
            )
            print("Created constraint. Response- {}".format(constraint_response))

    except botocore.exceptions.ClientError as e:
        print(e)
        print("Constraint creation failed. Error : {}".format(e))
        sys.exit(1)
    return "Success"

def accept_portfolio(event):
    portfolio_id = event['requestParameters']['portfolioId']
    sc_client = boto3.client('servicecatalog')
    try:
        #Accept portfolio shares
        sc_client.accept_portfolio_share(PortfolioId=portfolio_id)
    except botocore.exceptions.ClientError as e:
        print(e)
        sys.exit(1)

def process_event(event):
    message = event['Records'][0]['Sns']['Message']
    parsed_message = json.loads(message)
    print('parsed_message = ', parsed_message)
    return parsed_message['detail']

def main(event,context):
    #CREATE the following ENVIRONMENT VARIABLES
    # key = default_launch_constraint and value = <ROLE_NAME_FOR_SC_LAUNCH_CONSTRAINT>
    # key = default_iam_principal_role_name and value = <ROLE_NAME_FOR_SC_END_USER>
    print("Entered main function with event: {}".format(event))

    default_iam_principal_role_name = os.environ['default_iam_principal_role_name']
    default_launch_constraint = os.environ['default_launch_constraint']
    sts_client = boto3.client('sts')
    current_account = sts_client.get_caller_identity()['Account']
    sc_iam_role = ("arn:aws:iam::{}:role/{}".format(current_account,default_iam_principal_role_name))
    launch_constraint = ('{"RoleArn":"arn:aws:iam::'+str(current_account)+':role/'+default_launch_constraint+'"}')
    #Default share type is assumed as AWS_ORGANIZATIONS
    share_type = "AWS_ORGANIZATIONS"

    #Process SNS event
    sc_event = process_event(event)
    event_name = sc_event['eventName']

    #Check if Portfolio Share is at the AWS_ACCOUNT Level (not ORG sharing). If yes, check if its shared with the current account. If yes, accept the share.
    imported_account = sc_event['requestParameters'].get('accountId')
    if event_name == 'CreatePortfolioShare' and current_account == imported_account:
        print("Accepting portfolio share for account ", current_account)
        share_type = "IMPORTED"
        accept_portfolio(sc_event)

    print(sc_iam_role)
    print(launch_constraint)

    if(default_launch_constraint == None or default_iam_principal_role_name == None):
        print("Default launch constraint or IAM role missing, please provide in the Lambda environment variable")
        sys.exit(1)
    #Launching auto-import of AWS Service Catalog portfolios
    print("Looking for shared portfolios....")
    try:
        setup_portfolios(sc_iam_role,launch_constraint,share_type)
    except Exception as e:
        print("An error occured during auto-import of SC portfolios. Error: {}".format(e))
        sys.exit(1)
    return "Success"