
CREATE TABLE  IF NOT EXISTS activos(
    ticker TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    sector TEXT,
    divisa TEXT NOT NULL CHECK (length(divisa) = 3)
);



CREATE TABLE IF NOT EXISTS precios_diarios(
    fecha TEXT NOT NULL CHECK (fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    ticker TEXT NOT NULL,
    cierre REAL NOT NULL,
    volumen INTEGER,
    PRIMARY KEY (fecha, ticker),
    FOREIGN KEY (ticker) REFERENCES activos(ticker)
);



CREATE TABLE IF NOT EXISTS carteras(
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
);


CREATE TABLE IF NOT EXISTS operaciones(
    id INTEGER PRIMARY KEY,
    cartera_id INTEGER NOT NULL ,
    ticker TEXT NOT NULL ,
    fecha TEXT NOT NULL CHECK (fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    tipo TEXT NOT NULL CHECK (tipo IN ('compra', 'venta', 'dividendo')),
    cantidad REAL NOT NULL CHECK (cantidad >0),
    precio REAL NOT NULL CHECK (precio >=0),
    comision    REAL NOT NULL DEFAULT 0 CHECK (comision >= 0),
    FOREIGN KEY (cartera_id) REFERENCES carteras(id) ON DELETE RESTRICT,
    FOREIGN KEY (ticker)     REFERENCES activos(ticker)
);

CREATE INDEX IF NOT EXISTS idx_operaciones_cartera ON operaciones (cartera_id);



CREATE TABLE IF NOT EXISTS tipos_cambio (
    fecha   TEXT NOT NULL CHECK (fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),             
    divisa  TEXT NOT NULL CHECK (length(divisa) = 3 AND divisa <> 'EUR'),             
    tasa    REAL NOT NULL CHECK (tasa > 0),
    PRIMARY KEY (fecha, divisa)
);

CREATE TABLE IF NOT EXISTS eventos (
    fecha  TEXT NOT NULL CHECK (fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    ticker TEXT NOT NULL,
    tipo   TEXT NOT NULL CHECK (tipo IN ('split')),
    valor  REAL NOT NULL CHECK (valor > 0),
    PRIMARY KEY (fecha, ticker, tipo),
    FOREIGN KEY (ticker) REFERENCES activos(ticker)
);