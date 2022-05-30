terraform {
  backend "s3" {
    bucket  = "dallas-pets-alive-terraform"
    key     = "petfinder_sync.tfstate"
    region  = "us-east-2"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.27"
    }
  }

  required_version = ">= 0.14.9"
}

provider "aws" {
  profile = "default"
  region  = "us-east-2"
}

resource "aws_iam_role" "petfinder_sync_iam" {
  name = "petfinder_sync_iam"

  assume_role_policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [
      {
        "Action": "sts:AssumeRole",
        "Principal": {
          "Service": "lambda.amazonaws.com"
        },
        "Effect": "Allow",
        "Sid": ""
      }
    ]
  })
}

resource "aws_lambda_function" "petfinder_sync" {
  depends_on = [
    aws_cloudwatch_log_group.petfinder_sync_log_group,
  ]

  # If the file is not in the current working directory you will need to include a 
  # path.module in the filename.
  filename      = "petfinder_sync.zip"
  function_name = "petfinder_sync"
  role          = aws_iam_role.petfinder_sync_iam.arn
  handler       = "petfinder_sync.handler"

  source_code_hash = filebase64sha256("petfinder_sync.zip")

  runtime = "python3.9"
}

resource "aws_cloudwatch_log_group" "petfinder_sync_log_group" {
  name              = "/aws/lambda/petfinder_sync"
  retention_in_days = 90
}

resource "aws_iam_policy" "petfinder_sync_logging_policy" {
  name   = "petfinder_sync_logging_policy"
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        Action : [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect : "Allow",
        Resource : "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "petfinder_sync_logging_policy_attachment" {
  role = aws_iam_role.petfinder_sync_iam.id
  policy_arn = aws_iam_policy.petfinder_sync_logging_policy.arn
}

resource "aws_cloudwatch_event_rule" "petfinder_sync_event_rule" {
  name = "petfinder_sync_event_rule"
  description = "invoke petfinder sync once an hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "petfinder_sync_event_target" {
  arn = aws_lambda_function.petfinder_sync.arn
  rule = aws_cloudwatch_event_rule.petfinder_sync_event_rule.name
}

resource "aws_lambda_permission" "petfinder_sync_cloudwatch_permission" {
  statement_id = "AllowExecutionFromCloudWatch"
  action = "lambda:InvokeFunction"
  function_name = "petfinder_sync"
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.petfinder_sync_event_rule.arn
}
