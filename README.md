# Automatically import and sync local copies of AWS Service Catalog portfolios shared from a hub account

Customers have frequently asked for easier ways to setup AWS Service Catalog portfolios in their multi-account AWS environments. Last year, we took one step towards that goal when we launched the ability to share AWS Service Catalog portfolios to AWS Organizations, which allows you to specify an AWS account, organizational unit, or the entire organization that would have access to a SC portfolio from the hub account. 

However, in child accounts (linked accounts), there is still a requirement to create local portfolios from these shared portfolios so that you can assign local launch constraints and IAM entities to SC portfolios and products. In addition, any additions or removals of AWS SC products in the hub portfolios would need to be replicated in the child accounts. These activities require additional automation to be setup in customer accounts. 

To help you accelerate your implementation, I’d like to democratize a simple mechanism to auto import any shared portfolios from a hub account to the child account. This is based on proof of concepts that I have built for some of our customers recently. 

## Overview of sharing portfolios from the hub account
This solution does not scope for setting up of your AWS Service Catalog hub accounts. However, I would recommend that you automate setting up of your hub account SC portfolios using your preferred CICD tools. 

You can share AWS SC portfolios in 2 ways, see [documentation](https://docs.aws.amazon.com/servicecatalog/latest/dg/API_CreatePortfolioShare.html) for more details.

1. **Directly to a specified AWS account**
    * If you are sharing directly with an AWS account, the recipient account will need to accept this portfolio share (https://docs.aws.amazon.com/servicecatalog/latest/dg/API_AcceptPortfolioShare.html). 
2. **Directly to an AWS Organizations node**
    * Note: Today, these shares are only possible through the master payer account in your AWS Organizations.
    * If you are sharing your AWS Service Catalog portfolios from a hub account with AWS Organizations sharing, the child accounts will be able to view the shared portfolio automatically. There is no need to explicitly accept the portfolio share from the hub account in this case.

The solution sample provided here will accommodate both of these scenarios, and will be independent of the sharing ideology you follow in your environment.

## Overview of creating local portfolios in child accounts

Now, let’s assume you have set up your hub portfolios, shared them with other accounts, child accounts accepted the portfolio shares, and set up the IAM roles required in all the accounts required by AWS SC. At this point, it's fair to say that all the spoke accounts will only be able to list the portfolios that are shared with them. So, the only remaining task now is to create local copies of these portfolios and assign the pre-existing IAM roles per portfolio, and launch constraint per product.

To automate this task, we will build an AWS lambda function in all the child accounts in your environment which will be responsible for copying the shared portfolios into local copies, along with the required IAM assignments for products and portfolios. Additionally, this lambda will also maintain the latest configuration of all the local SC portfolios based on the state of the hub portfolios. For eg., if new products are added in the hub portfolios, they will be copied in the local account portfolios, and assigned a local launch constraint. 

Now, you may ask, how will the lambda know that there are changes in the hub portfolio? For this, we create an SNS topic in the hub portfolio, which will be triggered upon changes to AWS Service Catalog state using AWS CloudWatch events,  to notify all Lambda functions in your AWS environment of changes to hub portfolios.

## Architecture diagram
![auto-import-architecture](/images/autoimport.png)

## Setup
### Prerequisites
#### AWS Region
While this solution will work for any supported region, for this sample, please operate in **us-east-1**.
 
#### AWS CloudFormation StackSets setup 
To install this sample solution, you will need to ensure that you have the ability to use AWS CloudFormation StackSets to distribute the solution components to all your AWS accounts using automation. Please read [Prerequisites for Stack Set Operations](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-prereqs.html) to understand further. 

If you're not using [AWS Organizations automated deployments](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-orgs-enable-trusted-access.html), then you can grant Self-Managed Permissions to your AWS accounts in both hub and spoke accounts. This is done to ensure that your AWS hub account has permissions to execute AWS CloudFormation stacks in your spoke accounts.
(**Skip these 2 steps if you're using AWS Organizations automated deployments**)
1. _Create the StackSet administrator role in the hub account_  
  Run once in the hub account.  
  [![CreateStack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation#/stacks/new?stackName=IAM-StackSetAdministrator&templateURL=https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetAdministrationRole.yml) 
  
2. _Create the StackSet execution role in the spoke accounts_    
  Run once in each spoke account. Run once in the hub account if you wish to use AWS Service Catalog from the hub as well.  
  [![CreateStack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation#/stacks/new?stackName=IAM-StackSetExecution&templateURL=https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetExecutionRole.yml)


#### Set up your hub account to send updates using Amazon SNS and AWS CloudWatch events that will trigger AWS Lambda functions in all the spoke accounts

1. **Set up AWS CloudWatch event rules and Amazon SNS in your hub account using the following launch stack button**
 [![CreateStack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation#/stacks/new?stackName=ServiceCatalogHubSetup&templateURL=https://marketplace-sa-resources.s3.amazonaws.com/Auto-import-sc/templates/sc-sns-hub.yml)
    * In the `Outputs` section, make sure you note the ARN of the SNS topic created, you will use it in step 3.
    * **Please note**: This SNS topic has an overly permissive policy to account for the different ways you might share your AWS Service Catalog portfolio. Please lock down this policy based on your security requirements. Please read the official [docs](https://docs.aws.amazon.com/sns/latest/dg/sns-access-policy-use-cases.html) for further details on SNS access control
2. **Setup default IAM roles for AWS Service Catalog products in all AWS accounts (Run this sample from us-east-1 only)**
   * You can use AWS CloudFormation StackSets to create a default IAM principal and a default AWS SC launch constraint in all your AWS accounts. 
   * Go to AWS CloudFormation StackSets from the hub account, and use the following sample template to set up sample roles in all your accounts: [IAM demo setup template](https://s3.amazonaws.com/aws-service-catalog-reference-architectures/iam/sc-demosetup-iam.json)
      * If you are not using AWS Organizations, then you can use [self-managed permissions](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-prereqs-self-managed.html) to set up StackSets in all AWS accounts that need to auto import AWS SC portfolios shared to them
      * [Documentation](https://aws.amazon.com/blogs/aws/use-cloudformation-stacksets-to-provision-resources-across-multiple-aws-accounts-and-regions/) to learn how to use AWS CloudFormation StackSets
      * You will be prompted to enter the following parameters during the StackSets launch:
        * `StackSet name`: Enter an appropriate stackset name such as `aws-iam-roles-stackset`
      * These stacks will create the following IAM entities in every account, please note the names for step 3
        * IAM Principal Group: `ServiceCatalogEndusers`
        * IAM Principal Role: `ServiceCatalogEndusers`
        * SC Launch Constraint (Service Role): `SCEC2LaunchRole`
    * On the `Configure StackSet options` page, select `Service Managed Permissions` if you're using AWS Organizations, and want AWS CloudFormation to automatically deploy this stack to your designated accounts. If you're not using AWS Organizations, and want to self-manage stack permissions across accounts, select `Self service permissions`
    * On the `Set deployment options` page, select your deployment targets and regions. Click `Next`
    * On the `Review` page, review all the configuration options you've selected, click the `I acknowledge that AWS CloudFormation might create IAM resources with custom names` check box, and click `Submit`
3. **Set up the auto import lambda function in all AWS spoke accounts (Run this sample from us-east-1 only)**
   _Note: You should customize this implementation to set up individual launch constraints per product, and IAM principals per portfolio. You can do this by creating a map that your lambda function can read, or creating launch constraints that have the same name as the AWS SC product that the lambda function can read. The lambda function code is available in the resources/ folder of this repository_
   * Go to AWS CloudFormation StackSets from the hub account, and use the following sample template to set up a lambda function in all your accounts: https://marketplace-sa-resources.s3.amazonaws.com/Auto-import-sc/templates/sc-autopilot-setup.yml
      * If you are using AWS Organizations, you can set this up using `Enable Trusted Access with AWS Organizations` and not worry about setting up any AWS StackSet roles. To set up the required permissions for creating a stack set with service-managed permissions, see [Enable Trusted Access with AWS Organizations](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-orgs-enable-trusted-access.html)
      * If you are not using AWS Organizations, then you can use [self-managed permissions](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-prereqs-self-managed.html) to set up StackSets in all AWS accounts that need to auto import AWS SC portfolios shared to them
      * [Documentation](https://aws.amazon.com/blogs/aws/use-cloudformation-stacksets-to-provision-resources-across-multiple-aws-accounts-and-regions/) to learn how to use AWS CloudFormation StackSets.
    * You will be prompted to enter the following parameters during the StackSets launch:
      * `StackSet name`: Enter an appropriate stackset name such as `aws-sc-import-stackset`
      * `SourceBucket`: Name of the bucket where you will store the lambda function for this solution (region dependent)
      * `DefaultLaunchConstraint`: Default launch constraint name (NOT ARN) that will be applied to every AWS SC product. This role MUST exist in each account where the import lambda will run. If you are using IAM roles from step 2, then enter `SCEC2LaunchRole`
        * _Note: In the real world, you should modify the lambda code to add logic for launch constraints based on your requirements_
      * `LambdaFileName`: S3 key of the zip file containing the code for lambda function
      * `DefaultIAMPrincipalRoleName`: Default IAM role name (NOT ARN) who can access to imported SC portfolios in child accounts. This role MUST exist in each account where the import lambda will run. If you are using IAM roles from step 2, then enter `ServiceCatalogEndusers`
      * `SNSTopicArn`: From Step 1, get the ARN of the SNS topic in the hub account that will send notifications to this lambda from the hub account on changes
    * On the `Configure StackSet options` page, select `Service Managed Permissions` if you're using AWS Organizations, and want AWS CloudFormation to automatically deploy this stack to your designated accounts. If you're not using AWS Organizations, and want to self-manage stack permissions across accounts, select `Self service permissions`
    * On the `Set deployment options` page, select your deployment targets and regions (**us-east-1 only if using this sample**). Click `Next`.
    * On the `Review` page, review all the configuration options you've selected, click the `I acknowledge that AWS CloudFormation might create IAM resources with custom names` check box, and click `Submit`

## Steps to test

1. **Create an AWS Service Catalog Portfolio in your hub account**
   * Log in to your AWS Service Catalog hub account with `AdministratorAccess` or `AWSServiceCatalogAdminFullAccess` permissions
   * Open the [AWS Service Catalog console](https://console.aws.amazon.com/servicecatalog/) in us-east-1
   * If you are using the AWS Service Catalog administrator console for the first time, choose Get started to start the wizard for configuring a portfolio. Otherwise, choose Create portfolio
   * Type the following values:
        * `Portfolio name` – Engineering Tools
        * `Description` – Sample portfolio that contains a single product.
        * `Owner` – IT (it@example.com)
    * Click `Create`
2. **Create an AWS Service Catalog product in the portfolio created in the previous step**
     * Choose the name `Engineering Tools` to open the portfolio details page, and then choose Upload new product.
     * On the Enter product details page, type the following and then choose Next:
           * `Product name` – Linux Desktop
           * `Description` – Cloud development environment configured for engineering staff. Runs AWS Linux.
           * `Provided by` – IT
           * `Vendor` – (blank)
     * On the Enter support details page, type the following and then choose Next:
           * `Email contact` – ITSupport@example.com
           * `Support link` – https://wiki.example.com/IT/support
           * `Support description` – Contact the IT department for issues deploying or connecting to this product.
      * On the Version details page, choose Specify an Amazon S3 template URL, type the following, and then choose Next:
           * `Select template` – https://raw.githubusercontent.com/aws-samples/aws-service-catalog-reference-architectures/new_branch/ec2/sc-ec2-linux-nginx-nokey.json
           * `Version title` – v1.0
           * `Description` – Base Version
      * Click `Review` and then choose `Create Product`
3. **Share the portfolio with child accounts, or AWS Organizations**
   * On the portfolio details page, choose the `Share`
   * Click the `Share with new Account` button. Here, you have the option to share directly with an AWS Account, or within an AWS Organizations structure. Read more about [portfolio sharing](https://docs.aws.amazon.com/servicecatalog/latest/adminguide/catalogs_portfolios_sharing.html)
   * Enter the AWS Account numbers you want to share this product with, or the AWS Organization entity
4. **Check if child accounts have automatically imported the created portfolio and product**
   * Log in to any one of your AWS Service Catalog spoke/child accounts(ones you've shared the `Engineering Tools` portfolio in the previous step) with `AdministratorAccess` or `AWSServiceCatalogAdminFullAccess` permissions
   * Open the [AWS Service Catalog console](https://console.aws.amazon.com/servicecatalog/) in us-east-1
   * Click on the `Portfolios` link under the `Administration` section on the left navigation pane
   * You will see that the `Engineering Tools` portfolio exists here
   * Click on the `Engineering Tools` portfolio, where you will see the `Linux Desktop` product copied
   * On the portfolio details page, choose the `Constraints` tab. You will see the `SCEC2LaunchRole` constraint applied to the `Linux Desktop` product
   * On the portfolio details page, choose the `Groups, roles, and users` tab. You will see the `ServiceCatalogEndusers` IAM role applied to this portfolio 

### Notes
This sample does not include actions for deletion of AWS Service Catalog portfolios/products, but you can refer to the share actions and implement according to your business needs. Please create an issue if you'd like us to provide a sample for deletion as well.

[(Back to top)](#Automatically-import-and-sync-local-copies-of-AWS-Service-Catalog-portfolios-shared-from-a-hub-account)
## Contributing
Your contributions are always welcome! Please have a look at the [contribution guidelines](CONTRIBUTING.md) first. :tada:

[(Back to top)](#Automatically-import-and-sync-local-copies-of-AWS-Service-Catalog-portfolios-shared-from-a-hub-account)
## License
This sample code is made available under a modified MIT license. See the [LICENSE](LICENSE) file.

[(Back to top)](#Automatically-import-and-sync-local-copies-of-AWS-Service-Catalog-portfolios-shared-from-a-hub-account)
