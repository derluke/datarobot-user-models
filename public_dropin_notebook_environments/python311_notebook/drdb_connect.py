import datarobot as dr
import datarobotx.idp.datastore


def _find_existing_datastore(canonical_name: str) -> str:
    dss = dr.DataStore.list(typ="all")  # type: ignore
    datastore = [
        ds
        for ds in dss
        if ds.canonical_name is not None and ds.canonical_name == canonical_name
    ][0]
    return str(datastore.id)


datarobotx.idp.datastore._find_existing_datastore = _find_existing_datastore
from datarobotx.idp.datastore import get_or_create_datastore
from datarobotx.idp.datasource import get_or_create_datasource
from datarobotx.idp.datasets import get_or_create_dataset_from_datasource
from datarobotx.idp.credentials import get_replace_or_create_credential
from databricks.connect import DatabricksSession


class DBDRConnect:
    def __init__(self, dr_endpoint, dr_token, db_host, db_token, db_cluster_id):
        self.client = dr.Client(endpoint=dr_endpoint, token=dr_token)

        self.host = db_host
        self.token = db_token
        self.cluster_id = db_cluster_id

        self.session = (
            DatabricksSession.Builder()
            .host(db_host)
            .token(db_token)
            .clusterId(db_cluster_id)
            .getOrCreate()
        )
        self.datastore = self.get_or_create_datastore()
        self.credential = self.get_replace_or_create_credential()
        try:
            self.client.patch(
                f"credentials/{self.credential.credential_id}/associations/",
                json={
                    "credentialsToAdd": [
                        {"objectId": self.datastore.id, "objectType": "dataconnection"}
                    ]
                },
            )
        except:
            pass

    @classmethod
    def from_datastore(cls, datastore_name, db_token):
        client = dr.client.get_client()

        datastore = [
            ds
            for ds in dr.DataStore.list(typ="all")
            if datastore_name in ds.canonical_name
        ][0]

        data = datastore.params.fields
        http_path = next(
            item["value"] for item in data if item["id"] == "dbx.http_path"
        )
        server_hostname = next(
            item["value"] for item in data if item["id"] == "dbx.server_hostname"
        )

        # Extracting cluster ID from HTTP path
        db_cluster_id = http_path.split("/")[-1]

        # Constructing the db_host URL
        db_host = f"https://{server_hostname}"

        return cls(client.endpoint, client.token, db_host, db_token, db_cluster_id)

    def get_or_create_datastore(self):
        datastore = get_or_create_datastore(
            endpoint=self.client.endpoint,
            token=self.client.token,
            driver_id="652eb4562295307b93b0ce82",
            data_store_type="dr-database-v1",
            canonical_name="DBDRConnect Datastore",
            fields=[
                {
                    "id": "dbx.http_path",
                    "name": "HTTP path",
                    "value": f"sql/protocolv1/o/{self.host.split('//')[1].split('.')[0].split('-')[1]}/{self.cluster_id}",
                },
                {
                    "id": "dbx.server_hostname",
                    "name": "Server hostname",
                    "value": self.host.split("//")[1],
                },
            ],
        )
        return dr.DataStore.get(datastore)

    def get_replace_or_create_credential(self):
        credentials = get_replace_or_create_credential(
            endpoint=self.client.endpoint,
            token=self.client.token,
            name="DBDR Credentials",
            credential_type="databricks_access_token_account",
            databricks_access_token=self.token,
        )
        return dr.Credential.get(credentials)

    def get_or_create_datasource(self, catalog, schema, table, datasource_name):
        datasource = get_or_create_datasource(
            endpoint=self.client.endpoint,
            token=self.client.token,
            canonical_name=datasource_name,
            data_source_type="dr-database-v1",
            params={
                "catalog": catalog,
                "data_store_id": self.datastore.id,
                "schema": schema,
                "table": table,
            },
        )
        return dr.DataSource.get(datasource)

    def get_or_create_dataset_from_datasource(self, datasource, dataset_name):
        dataset = get_or_create_dataset_from_datasource(
            endpoint=self.client.endpoint,
            token=self.client.token,
            name=dataset_name,
            data_source_id=datasource.id,
            credential_id=self.credential.credential_id,
        )
        return dr.Dataset.get(dataset)

    def get_or_create_dataset_from_unity(self, catalog, schema, table, dataset_name):
        datasource = self.get_or_create_datasource(catalog, schema, table, dataset_name)
        dataset = self.get_or_create_dataset_from_datasource(datasource, dataset_name)
        return dataset
