Sources API setup on Mac using Docker
=====================================
1. Clone the repository and change to the sources-api directory:
```git clone https://github.com/RedHatInsights/sources-api```
2. Install ruby and rails. To install rails you might have to add `/usr/local/lib/ruby/gems/2.6.0/bin:/usr/local/opt/ruby/bin` to the beginning of your `$PATH`. I had to use `sudo` when using `gem install` but it may not be required:
```
brew install ruby
brew install libpq
gem install rails
gem install bundler
gem install pg
bundle install
```
3. Copy the following files:
```
cp v2_key.dev v2_key
cp config/database.dev.yml config/database.yml
```
4. Edit the database.yml to match sources database settings.  The differences are the port, username, and password (you have to add this line):
```
default: &default
  adapter: postgresql
  encoding: utf8
  host: localhost
  port: 15436
  username: postgres
  password: postgres
  pool: 5
  wait_timeout: 5
  min_messages: warning

development:
  <<: *default
  database: sources_api_development
  min_messages: notice

test:
  <<: *default
  database: sources_api_test

production:
  <<: *default
  database: sources_api_production
```
5. Create a docker-compose.yml that has the following:
```
version: '3'
services:
  sources-db:
    container_name: sources_db
    image: postgres:9.6
    environment:
    - POSTGRES_DB=sources
    - POSTGRES_USER=postgres
    - POSTGRES_PASSWORD=postgres
    ports:
      - 15436:5432
    volumes:
      - ./pg_data:/var/lib/pgsql/data
  zookeeper:
    image: confluentinc/cp-zookeeper
    environment:
      - ZOOKEEPER_CLIENT_PORT=32181
      - ZOOKEEPER_SERVER_ID=1
  kafka:
    image: confluentinc/cp-kafka
    ports:
      - 29092:29092
    depends_on:
      - zookeeper
    environment:
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:29092
      - KAFKA_BROKER_ID=1
      - KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1
      - KAFKA_ZOOKEEPER_CONNECT=zookeeper:32181
```
5. Bring up the services using `docker-compose up -d`
6. Start the backend sources server using:
```
bin/rake db:create db:migrate
QUEUE_PORT=29092 bundle exec rails s
```
7. Do a GET request to http://localhost:3000/api/v1.0/sources. You will need the following header:
```
x-rh-identity eyJpZGVudGl0eSI6IHsiYWNjb3VudF9udW1iZXIiOiAiMTAwMDEiLCAidHlwZSI6ICJVc2VyIiwgInVzZXIiOiB7InVzZXJuYW1lIjogInVzZXJfZGV2IiwgImVtYWlsIjogInVzZXJfZGV2QGZvby5jb20iLCAiaXNfb3JnX2FkbWluIjogdHJ1ZX19LCAiZW50aXRsZW1lbnRzIjogeyJvcGVuc2hpZnQiOiB7ImlzX2VudGl0bGVkIjogdHJ1ZX19fQ==
```
8. Change to the Koku directory, add `API_PATH_PREFIX=/api/cost-management` to your env file for Koku. Start Koku and let the server finish booting - you can view the `koku-server` logs to ensure that it is finished.
```
docker-compose up -d
docker-compose logs -f koku-server
```
9. Take down the `koku-server` and `sources-client`:
```
docker-compose stop koku-server sources-client
```
10. Start the `koku-server` with the following:
```
RABBITMQ_HOST=localhost RABBITMQ_PORT=5674 make serve
```
11. Start the `sources-client` with the following:
```
DJANGO_READ_DOT_ENV_FILE=True SOURCES=True RABBITMG_HOST=localhost RABBITMQ_PORT=5674  python koku/manage.py runserver 0.0.0.0:4000
```
12. Create a source using the following POSTS and PATCH, note that the `source_id` should match what you create in the first POST. Also make sure that you are using the header defined in step 7:
```
POST http://localhost:3000/api/v1.0/sources
{"name":"mskarbek-aws","source_type_id":"1"}

POST http://localhost:3000/api/v1.0/endpoints
{"role": "aws", "default": true, "source_id":"1"}

POST http://localhost:3000/api/v1.0/applications
{"application_type_id":"2","source_id":"1"}

POST http://localhost:3000/api/v1.0/authentications/
{"authtype":"arn","password":"arn:aws:iam::589173575009:role/CostManagement","resource_id":"1","resource_type":"Endpoint"}


PATCH http://localhost:4000/api/cost-management/v1/sources/1/
{
    "billing_source": {
        "bucket": "cost-usage-bucket"
    }
}

```
12. Trigger masu to start ingesting data and check that the providers and sources are created and that the `koku_uuid` and `sources_uuid` match in the sources endpoint:
```
GET http://127.0.0.1:5000/api/cost-management/v1/download/
GET http://localhost:8000/api/cost-management/v1/providers/
GET http://localhost:8000/api/cost-management/v1/sources/
```
Note the following port mapping :
```
Sources-API: 3000
Sources-client: 4000
Koku: 8000
```
