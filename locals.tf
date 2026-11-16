
locals {
  api_routes = toset([
    "users",
    "login",
    "orders",
    "payments",
    "checkout",
    "status",
    "support",
  ])
}
