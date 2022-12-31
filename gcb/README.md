# Building the bot

## Create the Artifact Registry repo for the container

```commandline
gcloud artifacts repositories create --location=us-east4 --repository-format=docker nft
```

## Submit a build to generate the container

```commandline
gcloud builds submit --region=us-east4 --config=gcb/build_bot.yaml .
```

## Running the bot

See the integration_tests folder for  information on how to test on fuji.
