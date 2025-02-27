"""
Simple Data Pipeline
"""
import sys
import time
from pathlib import Path
import logging
import sqlite3
import yaml
import pandas as pd


def create_connection(cfg:dict) -> sqlite3.Connection:
    """
    Utility function - creates connection to SQLite database
    :return: Connection object or None
    """
    conn = None
    database_file_path = Path(cfg['db']['file_path'])
    if not database_file_path.exists():
        logging.error('database file not found')
        sys.exit()
    else:
        try:
            conn = sqlite3.connect(database_file_path)
        except sqlite3.Error as error:
            logging.error(error)
            sys.exit()

    return conn


def configure_logging(cfg:dict):
    """
    Utility function - configures the data pipeline logging
    """
    # configure the logging
    log_file_path = Path(cfg['logging']['file_path'])
    logging.basicConfig(filename=log_file_path,
                        format='%(asctime)s -- [%(levelname)s]: %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


def get_config() -> dict:
    """
    Utility function returns Dict with config parameters
    :return: Dict with config parameters
    """
    with open("config.yaml", "r", encoding='utf-8') as ymlfile:
        cfg = yaml.safe_load(ymlfile)
    return cfg


def get_sales_by_month_sql(conn:sqlite3.Connection) -> pd.DataFrame:
    """
    Get total sales by month using SQL to aggregate the data
    :param: conn: connection to database
    :return: DataFrame with sales by month (Month, Quantity, TotalSales)
    """
    sql_query = """
        SELECT ROUND(SUM(ii.Quantity), 2) as Quantity,
        ROUND(SUM(ii.UnitPrice * ii.Quantity), 2) as TotalSales,
        CAST(strftime('%Y', i.InvoiceDate) as text) || "-" || 
            CAST(strftime('%m', i.InvoiceDate) as text) as Month
        FROM invoice_items ii
        INNER JOIN invoices i ON i.InvoiceId = ii.InvoiceId
		GROUP BY Month;
    """
    monthly_sales_df = pd.read_sql_query(sql_query, conn)
    return monthly_sales_df


def get_sales_by_month_pd(conn:sqlite3.Connection) -> pd.DataFrame:
    """
    Get total sales by month using Pandas to aggregate the data
    :param: conn: connection to database
    :return: DataFrame with sales by month (Month, Quantity, TotalSales)
    """
    sql_query = """
        SELECT ii.Quantity as Quantity,
        ii.UnitPrice as UnitPrice,
        i.InvoiceDate as InvoiceDate
        FROM invoice_items ii
        INNER JOIN invoices i ON i.InvoiceId = ii.InvoiceId;
    """
    monthly_sales_df = pd.read_sql_query(sql_query, conn)

    # add the month column in YYYY-MM format
    monthly_sales_df['Month'] = pd.to_datetime(monthly_sales_df['InvoiceDate']).dt.to_period('M')

    # drop the raw date column
    monthly_sales_df.drop('InvoiceDate', axis=1)

    monthly_sales_df['TotalPrice'] = monthly_sales_df['UnitPrice'] * monthly_sales_df['Quantity']

    #group by month and sum the Price and Quantity
    monthly_sales_df = monthly_sales_df.groupby('Month').agg(
        TotalSales=('TotalPrice', sum),
        Quantity=('Quantity', sum),
        Month=('Month','first'))

    return monthly_sales_df


def get_top_artists_by_sales(num_results:int, conn:sqlite3.Connection) -> pd.DataFrame:
    """
    Get the top N artists by total sales
    :param: num_results: the number of results to return
    :param: conn: connection to database
    :return: DataFrame with sales by Artist (Artist, Quantity, TotalSales)
    """
    sql_query = """
        SELECT ROUND(SUM(ii.Quantity), 2) as Quantity,
        ROUND(SUM(ii.UnitPrice * ii.Quantity), 2) as TotalSales,
        ar.Name as ArtistName
        FROM invoice_items ii
        INNER JOIN invoices i ON i.InvoiceId = ii.InvoiceId
        INNER JOIN tracks t ON t.TrackId = ii.TrackId
        INNER JOIN albums al ON al.AlbumId = t.AlbumId
        INNER JOIN artists ar ON ar.ArtistId = al.ArtistId
        GROUP BY ArtistName
        ORDER BY TotalSales DESC
        LIMIT ?
    """
    artist_sales_df = pd.read_sql_query(sql_query, conn)
    return artist_sales_df


def get_top_artists_by_sales(num_results:int, conn:sqlite3.Connection) -> pd.DataFrame:
    """
    Get the top N artists by total sales
    :param: num_results: the number of results to return
    :param: conn: connection to database
    :return: DataFrame with sales by Artist (Artist, Quantity, TotalSales)
    """
    sql_query = """
        SELECT Ii.Quantity as Quantity,
            ii.UnitPrice as UnitPrice,
            i.InvoiceDate as InvoiceDate,
            ar.Name as ArtistName
        FROM invoice_items ii
        INNER JOIN invoices i ON i.InvoiceId = ii.InvoiceId
        INNER JOIN tracks t ON t.TrackId = ii.TrackId
        INNER JOIN albums al ON al.AlbumId = t.AlbumId
        INNER JOIN artists ar ON ar.ArtistId = al.ArtistId
    """

    artist_sales_df = pd.read_sql_query(sql_query, conn)

    artist_sales_df['Month'] = pd.to_datetime(artist_sales_df['InvoiceDate']).dt.to_period('M')
    artist_sales_df.drop('InvoiceDate', axis=1)

    artist_sales_df['TotalSales'] = artist_sales_df['UnitPrice'] * artist_sales_df['Quantity']

    return artist_sales_df.groupby('ArtistName').agg(
        TotalSales=('TotalSales', sum),
        Quantity=('Quantity', sum),
        Month=('Month','first')).sort_values(by=['TotalSales'], ascending=False).head(num_results)


def get_tracks_by_genre(conn:sqlite3.Connection) -> pd.DataFrame:
    sql_query = """
        SELECT g.Name as Genre, COUNT(t.GenreId) as NumTracks
        FROM genres g
        INNER JOIN tracks t ON t.GenreId = g.GenreId
        GROUP BY t.GenreId
        ORDER BY NumTracks DESC;
    """
    return pd.read_sql_query(sql_query, conn)


def get_annual_sales_by_month(year:int, conn:sqlite3.Connection) -> pd.DataFrame:
    sql_query = """
        SELECT CAST(strftime('%m', i.InvoiceDate) as text) as Month,
            SUM(ii.Quantity) as Quantity,
            ROUND(SUM(ii.UnitPrice * ii.Quantity), 2) as TotalSales
        FROM invoice_items ii
        INNER JOIN invoices i ON i.InvoiceId = ii.InvoiceId
		WHERE CAST(strftime('%Y', i.InvoiceDate) as text) = ?
		GROUP BY Month;
    """
    return pd.read_sql_query(sql_query, conn, params=[year])


def get_sales_by_quarter(conn:sqlite3.Connection) -> pd.DataFrame:
    sql_query = """
        SELECT strftime('%Y', i.InvoiceDate) || 'Q' || FLOOR((strftime('%m', i.InvoiceDate) + 2) / 3 ) as Quarter,
            SUM(ii.Quantity) as Quantity,
            ROUND(SUM(ii.UnitPrice * ii.Quantity), 2) as TotalSales
        FROM invoice_items ii
        INNER JOIN invoices i ON i.InvoiceId = ii.InvoiceId
		GROUP BY Quarter;
    """
    return pd.read_sql_query(sql_query, conn)

def get_sales_by_year(conn:sqlite3.Connection) -> pd.DataFrame:
    sql_query = """
        SELECT strftime('%Y', i.InvoiceDate) as Year, 
            SUM(ii.Quantity) as Quantity,
            ROUND(SUM(ii.UnitPrice * ii.Quantity), 2) as TotalSales
        FROM invoice_items ii
        INNER JOIN invoices i ON i.InvoiceId = ii.InvoiceId
		GROUP BY Year;
    """
    return pd.read_sql_query(sql_query, conn)

def main():
    """
    Data Pipeline Process Control
    """
    start_time = time.time()
    cfg = get_config()
    configure_logging(cfg)
    logging.info("Starting data pipeline process")
    conn = create_connection(cfg)

    # run the data pipeline steps
    with conn:

        logging.info("Extracting sales data from database")

        # there are two example approaches for this function
        # Approach 1: format the month and calculate the total sales in SQL
        # monthly_sales_df = get_sales_by_month_sql(conn)
        # Approach 2: format the month and calculate the total sales in Pandas
        # monthly_sales_df = get_sales_by_month_pd(conn)

        # logging.info("Saving the sales data as CSV")
        # monthly_sales_df.to_csv(Path(cfg['extract_files']['sales_by_month_file_path']), index=False)

        logging.info("Extracting top 10 Artists by TotalSales")
        sales_by_artist_df = get_top_artists_by_sales(10, conn)

        logging.info("Saving sales by artist data as CSV")
        sales_by_artist_df.to_csv(Path(cfg['extract_files']['sales_by_artist_file_path']), index=False)

        # Challenge 1
        logging.info("Extracting tracks by genre")
        tracks_by_genre = get_tracks_by_genre(conn)

        logging.info("Saving tracks by genre data as CSV")
        tracks_by_genre.to_csv(Path(cfg['extract_files']['tracks_by_genre_file_path']), index=False)

        # Challenge 2
        year = 2012

        logging.info(f"Extracting sales by month for {year}")
        tracks_by_genre = get_annual_sales_by_month(year, conn)

        logging.info(f"Saving {year} sales data as CSV")
        tracks_by_genre.to_csv(Path(f'data/sales_by_month_{year}.csv'), index=False)

        # Challenge 3
        logging.info("Extracting sales by quarter")
        sales_by_quarter = get_sales_by_quarter(conn)

        logging.info("Saving sales by quarter data as CSV")
        sales_by_quarter.to_csv(Path(cfg['extract_files']['sales_by_quarter_file_path']), index=False)

        # Challenge 4
        num_results = 7

        logging.info(f"Extracting top {num_results} artists by sales")
        top_artists_by_sales = get_top_artists_by_sales(num_results, conn)

        logging.info(f"Saving top {num_results} artists  by sales as CSV")
        top_artists_by_sales.to_csv(Path(f'data/top_{num_results}_artists_by_sales.csv'), index=False)

        # Bonus Challenge
        logging.info("Extracting sales by year")
        sales_by_year = get_sales_by_year(conn)

        logging.info("Saving sales by year data as CSV")
        sales_by_year.to_csv(Path(cfg['extract_files']['sales_by_year_file_path']), index=False)

    conn.close()

    logging.info("Pipeline completed in %2.2f seconds" % (time.time() - start_time))
    logging.info("Finishing data pipeline process")


if __name__ == "__main__":
    main()
