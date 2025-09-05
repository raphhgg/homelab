
## Direct Run commands

Useful for testing

### Run Kometa immediatly

- Will run Kometa immediately rather than waiting
- Same as having `KOMETA_RUN=true` in `the docker-compose.yml`

```shell
docker exec -it kometa python3 kometa.py --run
```

### Test Collections

- Kometa will run only collections that are marked as test immediately
- Have `test: true` as first value in a collection

```shell
docker exec -it kometa python3 kometa.py --tests
```

```yml
collections:
  Detective & Crime Shows:
    test: true # Add this
    trakt_list: https://trakt.tv/users/raphh11/lists/crime-shows
    smart_label: added.desc
```

### Other commands

```shell
docker exec -it kometa python3 kometa.py --overlays-only
````

```shell
docker exec -it kometa python3 kometa.py --run-libraries "Movies" --overlays-only
````


```shell
docker exec -it kometa python3 kometa.py --run-libraries "Movies"
````