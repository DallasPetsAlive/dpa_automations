resource "aws_dynamodb_table" "featured-photos" {
  name           = "FeaturedPhotos"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "id"

  attribute {
    name = "id"
    type = "S"
  }
}
