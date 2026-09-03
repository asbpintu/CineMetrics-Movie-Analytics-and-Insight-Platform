SELECT DB_NAME() AS CurrentDatabase;


SELECT
    SCHEMA_NAME(schema_id) AS SchemaName,
    name AS TableName
FROM sys.tables
ORDER BY SchemaName, TableName;



SELECT
    s.name AS SchemaName,
    t.name AS TableName
FROM sys.tables t
JOIN sys.schemas s
    ON t.schema_id = s.schema_id
ORDER BY
    s.name,
    t.name;