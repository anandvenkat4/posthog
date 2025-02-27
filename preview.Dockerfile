FROM python:3.8-slim
ENV PYTHONUNBUFFERED 1
RUN mkdir /code
WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends gnupg \
    && apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8 \
    && echo "deb http://apt.postgresql.org/pub/repos/apt/ precise-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        postgresql redis-server \
    && apt-get purge -y gnupg \
    && rm -rf /var/lib/apt/lists/*

# START POSTGRES
# Run the next command as the ``postgres`` user created by the ``postgres-9.3`` package when it was ``apt-get installed``
USER postgres
# Create a PostgreSQL role named ``docker`` with ``docker`` as the password and
# then create a database `docker` owned by the ``docker`` role.
RUN    /etc/init.d/postgresql start &&\
    psql --command "CREATE USER posthog WITH SUPERUSER PASSWORD 'posthog';" &&\
    createdb posthog
# END POSGRES

USER root

RUN /etc/init.d/redis-server start

COPY requirements.txt /code/
# install dependencies but ignore any we don't need for dev environment
RUN pip install $(grep -ivE "drf-yasg|psycopg2|ipdb|mypy|ipython|ipdb|pip|djangorestframework-stubs|django-stubs|ipython-genutils|mypy-extensions|Pygments|typed-ast|jedi" requirements.txt) --no-cache-dir --compile\
    && pip install psycopg2-binary --no-cache-dir --compile\
    && pip uninstall ipython-genutils pip -y \
    && rm -rf /usr/local/lib/python3.8/site-packages/numpy/core/tests \
    && rm -rf /usr/local/lib/python3.8/site-packages/pandas/tests

COPY package.json /code/
COPY yarn.lock /code/
COPY webpack.config.js /code/
COPY postcss.config.js /code/
COPY .babelrc /code/
COPY frontend/ /code/frontend
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sL https://deb.nodesource.com/setup_12.x  | bash - \
    && apt-get install nodejs -y --no-install-recommends \
    && npm install -g yarn@1 \
    && yarn --frozen-lockfile \
    && yarn build \
    && yarn cache clean \
    && npm uninstall -g yarn \
    && apt-get purge -y nodejs curl \
    && rm -rf node_modules \
	&& rm -rf /var/lib/apt/lists/* \
    && rm -rf frontend/dist/*.map

COPY . /code/

RUN DATABASE_URL='postgres:///' REDIS_URL='redis:///' python manage.py collectstatic --noinput

RUN /etc/init.d/postgresql start\
    && DATABASE_URL=postgres://posthog:posthog@localhost:5432/posthog REDIS_URL='redis:///' python manage.py migrate\
    && /etc/init.d/postgresql stop

VOLUME /var/lib/postgresql
EXPOSE 8000
ENTRYPOINT ["./bin/docker-preview"]
