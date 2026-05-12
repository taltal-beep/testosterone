Feature: Mock API flows — health, errors, and auth (part 1)

  Background:
    Given the mock API client is ready

  Scenario: Root returns 200
    When I GET "/"
    Then the status code should be 200

  Scenario: Slow endpoint completes with 200
    When I GET "/slow"
    Then the status code should be 200

  Scenario: Forced error endpoint returns 500
    When I GET "/error"
    Then the status code should be 500

  Scenario: Flaky endpoint returns 200 or 500
    When I GET "/flaky"
    Then the status code should be one of 200, 500

  Scenario: Chaos endpoint returns 200, 401, or 500
    When I GET "/chaos"
    Then the status code should be one of 200, 401, 500

  Scenario: Secure without token returns 401
    When I GET "/secure"
    Then the status code should be 401

  Scenario: Admin without token returns 401
    When I GET "/admin"
    Then the status code should be 401

  Scenario: Login returns 200 and a token
    When I POST to "/login" with JSON
      """
      {"username": "alice"}
      """
    Then the status code should be 200
    And the JSON field "token" should exist

  Scenario: Secure with bearer returns 200
    Given I am logged in as "alice"
    When I GET "/secure" as authenticated user
    Then the status code should be 200

  Scenario: Admin with bearer returns 200
    Given I am logged in as "bob"
    When I GET "/admin" as authenticated user
    Then the status code should be 200

  Scenario: Submit accepts JSON payload
    When I POST to "/submit" with JSON
      """
      {"kind": "test", "value": 42}
      """
    Then the status code should be 200
    And the JSON field "received" should be true

  Scenario: Items list is empty initially
    When I GET "/items"
    Then the status code should be 200

  Scenario: Create item returns 200
    When I POST to "/items" with JSON
      """
      {"name": "alpha", "meta": {"tier": "gold"}}
      """
    Then the status code should be 200
    And the JSON field "created" should be true

  Scenario: Get created item by id
    When I POST to "/items" with JSON
      """
      {"name": "beta"}
      """
    Then the status code should be 200
    When I GET "/items/1"
    Then the status code should be 200

  Scenario: Delete item returns 200
    When I POST to "/items" with JSON
      """
      {"name": "gamma"}
      """
    Then the status code should be 200
    When I DELETE "/items/1"
    Then the status code should be 200

  Scenario: Deleted item returns 404
    When I POST to "/items" with JSON
      """
      {"name": "delta"}
      """
    Then the status code should be 200
    When I DELETE "/items/1"
    Then the status code should be 200
    When I GET "/items/1"
    Then the status code should be 404
