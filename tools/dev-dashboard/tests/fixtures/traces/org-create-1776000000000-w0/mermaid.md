sequenceDiagram
    actor User
    User->>API: POST /orgs
    API->>Repo: create_org()
    Repo-->>API: Org
    API-->>User: 201
