# C4-PlantUML Sprite Mappings

Load this reference **only if PlantUML was selected in Phase 1 Q9**.

After exporting `.puml` files, enhance every one with sprite icons using
`UpdateElementStyle` for colors and `$sprite` for icons.

## Sprite library headers (inject after `@startuml`)

```plantuml
!define DEVICONS https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/v2.4.0/devicons2
!define FONTAWESOME https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/v2.4.0/font-awesome-5
```

## Color overrides (use UpdateElementStyle — not AddPersonTag / AddSystemTag)

```plantuml
UpdateElementStyle("Person",          $bgColor="#08427B", $fontColor="#ffffff", $borderColor="#052E56")
UpdateElementStyle("Software System", $bgColor="#1168BD", $fontColor="#ffffff", $borderColor="#0B4884")
UpdateElementStyle("External System", $bgColor="#6B6B6B", $fontColor="#ffffff", $borderColor="#4A4A4A")
UpdateElementStyle("Container",       $bgColor="#438DD5", $fontColor="#ffffff", $borderColor="#2E6295")
UpdateElementStyle("ContainerDb",     $bgColor="#2E6DA4", $fontColor="#ffffff", $borderColor="#204C72")
UpdateElementStyle("Component",       $bgColor="#85BBF0", $fontColor="#1A1A1A", $borderColor="#5D82A8")
UpdateElementStyle("Observability",   $bgColor="#7B5EA7", $fontColor="#ffffff", $borderColor="#5A3F8A")
UpdateRelStyle($lineColor="#5A5A5A",  $textColor="#5A5A5A", $offsetX="0", $offsetY="-10", $fontSize="14")
```

## Technology → sprite mapping

| Technology | Include | `$sprite` |
|---|---|---|
| React | `!include DEVICONS/react.puml` | `react` |
| Angular | `!include DEVICONS/angularjs.puml` | `angularjs` |
| Vue.js | `!include DEVICONS/vuejs.puml` | `vuejs` |
| Node.js / Express | `!include DEVICONS/nodejs.puml` | `nodejs` |
| Java / Spring Boot | `!include DEVICONS/java.puml` | `java` |
| Python | `!include DEVICONS/python.puml` | `python` |
| .NET / C# | `!include DEVICONS/dotnetcore.puml` | `dotnetcore` |
| Go | `!include DEVICONS/go.puml` | `go` |
| PostgreSQL | `!include DEVICONS/postgresql.puml` | `postgresql` |
| MySQL | `!include DEVICONS/mysql.puml` | `mysql` |
| MongoDB | `!include DEVICONS/mongodb.puml` | `mongodb` |
| Redis | `!include DEVICONS/redis.puml` | `redis` |
| Kafka | `!include DEVICONS/apachekafka.puml` | `apachekafka` |
| RabbitMQ | `!include DEVICONS/rabbitmq.puml` | `rabbitmq` |
| Docker | `!include DEVICONS/docker.puml` | `docker` |
| Kubernetes | `!include DEVICONS/kubernetes.puml` | `kubernetes` |
| AWS | `!include FONTAWESOME/aws.puml` | `aws` |
| Azure | `!include DEVICONS/azure.puml` | `azure` |
| GCP | `!include DEVICONS/googlecloud.puml` | `googlecloud` |
| Nginx | `!include DEVICONS/nginx.puml` | `nginx` |
| GraphQL | `!include DEVICONS/graphql.puml` | `graphql` |
| Elasticsearch | `!include DEVICONS/elasticsearch.puml` | `elasticsearch` |

## Element macro rules

| Element | Macro |
|---|---|
| Service / API container | `Container(id, "Name", "Tech", "Desc", $sprite="X")` |
| Database container | `ContainerDb(id, "Name", "Tech", "Desc", $sprite="X")` |
| Queue container | `ContainerQueue(id, "Name", "Tech", "Desc", $sprite="X")` |
| Component | `Component(id, "Name", "Tech", "Desc")` — no sprite |
| Person | `Person(id, "Name", "Desc")` — no sprite |
| External system | `System_Ext(id, "Name", "Desc")` — no sprite |
