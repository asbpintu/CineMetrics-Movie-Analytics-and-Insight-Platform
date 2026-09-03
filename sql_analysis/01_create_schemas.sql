CREATE DATABASE CineMetrics;
GO



USE CineMetrics;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'stg'
)
BEGIN
    EXEC('CREATE SCHEMA stg');
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'dim'
)
BEGIN
    EXEC('CREATE SCHEMA dim');
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'bridge'
)
BEGIN
    EXEC('CREATE SCHEMA bridge');
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'fact'
)
BEGIN
    EXEC('CREATE SCHEMA fact');
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'reporting'
)
BEGIN
    EXEC('CREATE SCHEMA reporting');
END
GO