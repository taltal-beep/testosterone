Feature: Mock API flows — items, auth headers, and repeats (part 2)

  Background:
    Given the mock API client is ready

  Scenario: Root still returns 200 after other calls
    When I GET "/"
    Then the status code should be 200

  Scenario: Second root check
    When I GET "/"
    Then the status code should be 200

  Scenario: Items endpoint returns 200 with empty list after reset
    When I GET "/items"
    Then the status code should be 200

  Scenario: Create two items and list them
    When I POST to "/items" with JSON
      """
      {"name": "one"}
      """
    Then the status code should be 200
    When I POST to "/items" with JSON
      """
      {"name": "two"}
      """
    Then the status code should be 200
    When I GET "/items"
    Then the status code should be 200

  Scenario: Get first item by id
    When I POST to "/items" with JSON
      """
      {"name": "first"}
      """
    Then the status code should be 200
    When I GET "/items/1"
    Then the status code should be 200

  Scenario: Get second item by id
    When I POST to "/items" with JSON
      """
      {"name": "a"}
      """
    Then the status code should be 200
    When I POST to "/items" with JSON
      """
      {"name": "b"}
      """
    Then the status code should be 200
    When I GET "/items/2"
    Then the status code should be 200

  Scenario: Login as charlie
    When I POST to "/login" with JSON
      """
      {"username": "charlie"}
      """
    Then the status code should be 200

  Scenario: Login as dana
    When I POST to "/login" with JSON
      """
      {"username": "dana"}
      """
    Then the status code should be 200

  Scenario: Secure with invalid bearer returns 401
    When I request GET "/secure" with Authorization "Bearer invalid-token"
    Then the status code should be 401

  Scenario: Admin with malformed bearer returns 401
    When I request GET "/admin" with Authorization "not-bearer xyz"
    Then the status code should be 401

  Scenario: Submit empty object
    When I POST to "/submit" with JSON
      """
      {}
      """
    Then the status code should be 200

  Scenario: Submit nested object
    When I POST to "/submit" with JSON
      """
      {"a": {"b": [1, 2, 3]}}
      """
    Then the status code should be 200

  Scenario: Create item with default name
    When I POST to "/items" with JSON
      """
      {}
      """
    Then the status code should be 200

  Scenario: Another flaky sample
    When I GET "/flaky"
    Then the status code should be one of 200, 500

  Scenario: Another chaos sample
    When I GET "/chaos"
    Then the status code should be one of 200, 401, 500

  Scenario: Delete missing item returns 404
    When I DELETE "/items/999"
    Then the status code should be 404

  Scenario: Get missing item returns 404
    When I GET "/items/999"
    Then the status code should be 404

  Scenario: Login default username path
    When I POST to "/login" with JSON
      """
      {}
      """
    Then the status code should be 200
    And the JSON field "token" should exist
