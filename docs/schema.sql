CREATE EXTENSION IF NOT EXISTS postgis;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS btree_gist;


CREATE TABLE banner (
	position INTEGER NOT NULL, 
	eyebrow VARCHAR(80) NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	art VARCHAR(20) NOT NULL, 
	href VARCHAR(500) NOT NULL, 
	active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (position BETWEEN 1 AND 6), 
	UNIQUE (position)
)

;


CREATE TABLE category (
	name VARCHAR(80) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
)

;


CREATE TABLE geo_cache (
	query VARCHAR(200) NOT NULL, 
	results JSONB NOT NULL, 
	expires TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (query)
)

;


CREATE TABLE plan (
	name VARCHAR(16) NOT NULL, 
	products INTEGER NOT NULL, 
	reels INTEGER NOT NULL, 
	hours INTEGER NOT NULL, 
	PRIMARY KEY (name), 
	CHECK (products > 0 AND reels >= 0 AND hours >= 0)
)

;


CREATE TABLE rate (
	metal VARCHAR(10) NOT NULL, 
	value NUMERIC(18, 4) NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (metal), 
	CHECK (value > 0), 
	CHECK (metal IN ('Gold','Silver'))
)

;


CREATE TABLE tag (
	name VARCHAR(60) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
)

;


CREATE TABLE throttle (
	key VARCHAR(128) NOT NULL, 
	count INTEGER NOT NULL, 
	expires TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
)

;


CREATE TABLE unit (
	name VARCHAR(80) NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
	grams NUMERIC(20, 10) NOT NULL, 
	active BOOLEAN NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (grams > 0), 
	UNIQUE (name), 
	UNIQUE (symbol)
)

;


CREATE TABLE "user" (
	phone VARCHAR(20) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(254), 
	password_hash TEXT NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (role IN ('merchant','admin')), 
	UNIQUE (phone)
)

;


CREATE TABLE audit (
	actor_id UUID, 
	action VARCHAR(80) NOT NULL, 
	entity_id VARCHAR(80) NOT NULL, 
	detail JSONB NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES "user" (id)
)

;

CREATE INDEX ix_audit_action ON audit (action);


CREATE TABLE mutation (
	key UUID NOT NULL, 
	actor_id UUID NOT NULL, 
	path VARCHAR(200) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key), 
	FOREIGN KEY(actor_id) REFERENCES "user" (id)
)

;


CREATE TABLE store (
	owner_id UUID NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	phone VARCHAR(20) NOT NULL, 
	address VARCHAR(500) NOT NULL, 
	latitude NUMERIC(10, 7) NOT NULL, 
	longitude NUMERIC(10, 7) NOT NULL, 
	location geography(POINT,4326) NOT NULL, 
	surplus NUMERIC(18, 4) NOT NULL, 
	verification VARCHAR(16) NOT NULL, 
	active BOOLEAN NOT NULL, 
	plan_name VARCHAR(16) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (surplus >= 0), 
	CHECK (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180), 
	CHECK (verification IN ('pending','verified','rejected')), 
	UNIQUE (owner_id), 
	FOREIGN KEY(owner_id) REFERENCES "user" (id), 
	FOREIGN KEY(plan_name) REFERENCES plan (name)
)

;

CREATE INDEX ix_store_verification ON store (verification);

CREATE INDEX idx_store_location ON store USING gist (location);


CREATE TABLE product (
	store_id UUID NOT NULL, 
	category_id UUID NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	description TEXT NOT NULL, 
	metal VARCHAR(10) NOT NULL, 
	purity NUMERIC(12, 10) NOT NULL, 
	weight NUMERIC(16, 6) NOT NULL, 
	making NUMERIC(18, 4) NOT NULL, 
	fixed NUMERIC(18, 4) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	search_text TEXT NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (weight > 0 AND purity > 0 AND purity <= 1 AND making >= 0 AND fixed >= 0), 
	CHECK (status IN ('draft','published','archived','suspended','excess')), 
	FOREIGN KEY(store_id) REFERENCES store (id), 
	FOREIGN KEY(category_id) REFERENCES category (id), 
	FOREIGN KEY(metal) REFERENCES rate (metal)
)

;

CREATE INDEX ix_product_store_id ON product (store_id);

CREATE INDEX ix_product_category_id ON product (category_id);

CREATE INDEX ix_product_metal ON product (metal);

CREATE INDEX ix_product_catalogue ON product (status, metal, category_id, created_at);

CREATE INDEX ix_product_status ON product (status);


CREATE TABLE feature (
	store_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	start TIMESTAMP WITH TIME ZONE NOT NULL, 
	"end" TIMESTAMP WITH TIME ZONE NOT NULL, 
	slot INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK ("end" > start), 
	CHECK (slot BETWEEN 1 AND 6), 
	FOREIGN KEY(store_id) REFERENCES store (id), 
	FOREIGN KEY(product_id) REFERENCES product (id)
)

;

CREATE INDEX ix_feature_start ON feature (start);

CREATE INDEX ix_feature_store_id ON feature (store_id);


CREATE TABLE media (
	product_id UUID, 
	store_id UUID NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	source VARCHAR(120) NOT NULL, 
	output VARCHAR(120), 
	thumbnail VARCHAR(120), 
	variants JSONB NOT NULL, 
	error VARCHAR(500), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (kind IN ('image','reel','document','payment')), 
	CHECK (status IN ('queued','processing','ready','failed','suspended','excess')), 
	FOREIGN KEY(product_id) REFERENCES product (id), 
	FOREIGN KEY(store_id) REFERENCES store (id)
)

;

CREATE INDEX ix_media_store_id ON media (store_id);

CREATE INDEX ix_media_product_id ON media (product_id);


CREATE TABLE product_tag (
	product_id UUID NOT NULL, 
	tag_id UUID NOT NULL, 
	PRIMARY KEY (product_id, tag_id), 
	FOREIGN KEY(product_id) REFERENCES product (id), 
	FOREIGN KEY(tag_id) REFERENCES tag (id)
)

;


CREATE TABLE delivery (
	feature_id UUID NOT NULL, 
	day DATE NOT NULL, 
	impressions BIGINT NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (feature_id, day), 
	FOREIGN KEY(feature_id) REFERENCES feature (id)
)

;

CREATE INDEX ix_delivery_feature_id ON delivery (feature_id);


CREATE TABLE job (
	media_id UUID NOT NULL, 
	state VARCHAR(16) NOT NULL, 
	attempts INTEGER NOT NULL, 
	leased_at TIMESTAMP WITH TIME ZONE, 
	token UUID, 
	error VARCHAR(500), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (media_id), 
	FOREIGN KEY(media_id) REFERENCES media (id)
)

;

CREATE INDEX ix_job_state ON job (state);


CREATE TABLE upgrade (
	store_id UUID NOT NULL, 
	plan_name VARCHAR(16) NOT NULL, 
	evidence_id UUID NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES store (id), 
	FOREIGN KEY(plan_name) REFERENCES plan (name), 
	FOREIGN KEY(evidence_id) REFERENCES media (id)
)

;

CREATE INDEX ix_product_search_trgm ON product USING gin (search_text gin_trgm_ops);

CREATE INDEX ix_store_name_trgm ON store USING gin (name gin_trgm_ops);

ALTER TABLE feature ADD CONSTRAINT feature_slot_no_overlap EXCLUDE USING gist (slot WITH =, tstzrange(start, "end", '[)') WITH &&) WHERE (status = 'scheduled');

CREATE FUNCTION protect_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Audit events are immutable'; END $$;

CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit FOR EACH ROW EXECUTE FUNCTION protect_audit();
