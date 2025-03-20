terraform {
  backend "s3" {
    bucket  = "dallas-pets-alive-terraform"
    key     = "jotform_alerts.tfstate"
    region  = "us-east-2"
  }

  required_providers {
    aws = {
      source = "hashicorp/aws"
      version = "5.91.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.2.0"
    }
  }

  required_version = ">= 0.14.9"
}

provider "aws" {
  region  = "us-east-2"
}

resource "aws_s3_bucket" "jotform_alerts_bucket" {
  bucket = "jotform-alerts-dpa-bucket"
}

resource "aws_iam_role" "jotform_alerts_iam" {
  name = "jotform_alerts_iam"

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

resource "aws_iam_policy" "jotform_alerts_policy" {
  name = "jotform_alerts_webhook_policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      }, {
        Action   = ["sns:Publish*"]
        Effect   = "Allow"
        Resource = "arn:aws:sns:us-east-2:832971646995:Default_CloudWatch_Alarms_Topic"
      }, {
        Action   = ["ses:SendEmail"]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "jotform_alerts_policy" {
  role       = aws_iam_role.jotform_alerts_iam.name
  policy_arn = aws_iam_policy.jotform_alerts_policy.arn
}
