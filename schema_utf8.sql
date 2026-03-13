--
-- PostgreSQL database dump
--

\restrict glDwmuf30CuiyDX7bcrRDO5aq2AUcPor1IsDbpgBHgMXmsh1kZ4HOrtP5Oad6sL

-- Dumped from database version 16.13 (Debian 16.13-1.pgdg13+1)
-- Dumped by pg_dump version 16.13 (Debian 16.13-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: enroll_status_enum; Type: TYPE; Schema: public; Owner: mugang
--

CREATE TYPE public.enroll_status_enum AS ENUM (
    'COMPLETED',
    'CANCELED',
    'BASKET'
);


ALTER TYPE public.enroll_status_enum OWNER TO mugang;

--
-- Name: lecture_category; Type: TYPE; Schema: public; Owner: mugang
--

CREATE TYPE public.lecture_category AS ENUM (
    '전공필수',
    '전공선택',
    '교양필수',
    '교양선택',
    '교직',
    '공통'
);


ALTER TYPE public.lecture_category OWNER TO mugang;

--
-- Name: role_enum; Type: TYPE; Schema: public; Owner: mugang
--

CREATE TYPE public.role_enum AS ENUM (
    'STUDENT',
    'STAFF'
);


ALTER TYPE public.role_enum OWNER TO mugang;

--
-- Name: status_enum; Type: TYPE; Schema: public; Owner: mugang
--

CREATE TYPE public.status_enum AS ENUM (
    '재학',
    '휴학',
    '재직',
    '퇴직'
);


ALTER TYPE public.status_enum OWNER TO mugang;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: depart_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.depart_tb (
    dept_no bigint NOT NULL,
    college character varying(50) NOT NULL,
    depart character varying(255) NOT NULL,
    office_tel character varying(50) NOT NULL
);


ALTER TABLE public.depart_tb OWNER TO mugang;

--
-- Name: depart_tb_dept_no_seq; Type: SEQUENCE; Schema: public; Owner: mugang
--

CREATE SEQUENCE public.depart_tb_dept_no_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.depart_tb_dept_no_seq OWNER TO mugang;

--
-- Name: depart_tb_dept_no_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mugang
--

ALTER SEQUENCE public.depart_tb_dept_no_seq OWNED BY public.depart_tb.dept_no;


--
-- Name: enroll_schedule_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.enroll_schedule_tb (
    id integer NOT NULL,
    day_number integer NOT NULL,
    open_datetime timestamp without time zone,
    close_datetime timestamp without time zone,
    restriction_type character varying(30) NOT NULL,
    is_active boolean,
    updated_at timestamp without time zone
);


ALTER TABLE public.enroll_schedule_tb OWNER TO mugang;

--
-- Name: enroll_schedule_tb_id_seq; Type: SEQUENCE; Schema: public; Owner: mugang
--

CREATE SEQUENCE public.enroll_schedule_tb_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.enroll_schedule_tb_id_seq OWNER TO mugang;

--
-- Name: enroll_schedule_tb_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mugang
--

ALTER SEQUENCE public.enroll_schedule_tb_id_seq OWNED BY public.enroll_schedule_tb.id;


--
-- Name: enroll_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.enroll_tb (
    enroll_no bigint NOT NULL,
    loginid bigint,
    lecture_id bigint,
    sche_no bigint,
    enroll_status public.enroll_status_enum,
    status character varying(20),
    createdat timestamp without time zone
);


ALTER TABLE public.enroll_tb OWNER TO mugang;

--
-- Name: enroll_tb_enroll_no_seq; Type: SEQUENCE; Schema: public; Owner: mugang
--

CREATE SEQUENCE public.enroll_tb_enroll_no_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.enroll_tb_enroll_no_seq OWNER TO mugang;

--
-- Name: enroll_tb_enroll_no_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mugang
--

ALTER SEQUENCE public.enroll_tb_enroll_no_seq OWNED BY public.enroll_tb.enroll_no;


--
-- Name: grade_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.grade_tb (
    id integer NOT NULL,
    user_id bigint,
    enrollment_id bigint,
    grade_letter character varying(5),
    semester character varying(20),
    is_retake boolean
);


ALTER TABLE public.grade_tb OWNER TO mugang;

--
-- Name: grade_tb_id_seq; Type: SEQUENCE; Schema: public; Owner: mugang
--

CREATE SEQUENCE public.grade_tb_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.grade_tb_id_seq OWNER TO mugang;

--
-- Name: grade_tb_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mugang
--

ALTER SEQUENCE public.grade_tb_id_seq OWNED BY public.grade_tb.id;


--
-- Name: lecture_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.lecture_tb (
    lecture_id integer NOT NULL,
    course_no character varying(20),
    subject character varying(200) NOT NULL,
    department character varying(100),
    dept_no bigint,
    lec_grade character varying(10),
    credit integer,
    professor character varying(50),
    type public.lecture_category,
    capacity integer,
    count integer,
    waitlist_capacity integer,
    version integer,
    classroom character varying(100)
);


ALTER TABLE public.lecture_tb OWNER TO mugang;

--
-- Name: lecture_tb_lecture_id_seq; Type: SEQUENCE; Schema: public; Owner: mugang
--

CREATE SEQUENCE public.lecture_tb_lecture_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lecture_tb_lecture_id_seq OWNER TO mugang;

--
-- Name: lecture_tb_lecture_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mugang
--

ALTER SEQUENCE public.lecture_tb_lecture_id_seq OWNED BY public.lecture_tb.lecture_id;


--
-- Name: notice_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.notice_tb (
    id character varying NOT NULL,
    title character varying(255) NOT NULL,
    content character varying NOT NULL,
    author_id bigint,
    created_at timestamp without time zone
);


ALTER TABLE public.notice_tb OWNER TO mugang;

--
-- Name: notification_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.notification_tb (
    id character varying NOT NULL,
    user_id bigint,
    message character varying(255) NOT NULL,
    is_read boolean,
    created_at timestamp without time zone
);


ALTER TABLE public.notification_tb OWNER TO mugang;

--
-- Name: overenroll_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.overenroll_tb (
    over_no bigint NOT NULL,
    user_no bigint,
    lecture_id bigint,
    sche_no bigint,
    reason character varying(255),
    loginid character varying(50) NOT NULL
);


ALTER TABLE public.overenroll_tb OWNER TO mugang;

--
-- Name: overenroll_tb_over_no_seq; Type: SEQUENCE; Schema: public; Owner: mugang
--

CREATE SEQUENCE public.overenroll_tb_over_no_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.overenroll_tb_over_no_seq OWNER TO mugang;

--
-- Name: overenroll_tb_over_no_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mugang
--

ALTER SEQUENCE public.overenroll_tb_over_no_seq OWNED BY public.overenroll_tb.over_no;


--
-- Name: schedule_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.schedule_tb (
    sche_no integer NOT NULL,
    lecture_id integer,
    day_of_week character varying(1),
    start_min integer,
    end_min integer,
    start_time time without time zone,
    end_time time without time zone,
    classroom character varying(50)
);


ALTER TABLE public.schedule_tb OWNER TO mugang;

--
-- Name: schedule_tb_sche_no_seq; Type: SEQUENCE; Schema: public; Owner: mugang
--

CREATE SEQUENCE public.schedule_tb_sche_no_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.schedule_tb_sche_no_seq OWNER TO mugang;

--
-- Name: schedule_tb_sche_no_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mugang
--

ALTER SEQUENCE public.schedule_tb_sche_no_seq OWNED BY public.schedule_tb.sche_no;


--
-- Name: system_config_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.system_config_tb (
    key character varying(100) NOT NULL,
    value character varying(255) NOT NULL
);


ALTER TABLE public.system_config_tb OWNER TO mugang;

--
-- Name: user_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.user_tb (
    user_no bigint NOT NULL,
    loginid character varying(50) NOT NULL,
    password character varying(255) NOT NULL,
    role public.role_enum NOT NULL,
    user_name character varying(50) NOT NULL,
    grade integer,
    dept_no bigint,
    user_status public.status_enum NOT NULL,
    birth_date date,
    email character varying(150),
    phone character varying(20),
    is_first_login boolean,
    created_at timestamp without time zone
);


ALTER TABLE public.user_tb OWNER TO mugang;

--
-- Name: user_tb_user_no_seq; Type: SEQUENCE; Schema: public; Owner: mugang
--

CREATE SEQUENCE public.user_tb_user_no_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_tb_user_no_seq OWNER TO mugang;

--
-- Name: user_tb_user_no_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mugang
--

ALTER SEQUENCE public.user_tb_user_no_seq OWNED BY public.user_tb.user_no;


--
-- Name: waitlist_tb; Type: TABLE; Schema: public; Owner: mugang
--

CREATE TABLE public.waitlist_tb (
    id character varying NOT NULL,
    lecture_id integer,
    user_id bigint,
    status character varying(20),
    created_at timestamp without time zone
);


ALTER TABLE public.waitlist_tb OWNER TO mugang;

--
-- Name: depart_tb dept_no; Type: DEFAULT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.depart_tb ALTER COLUMN dept_no SET DEFAULT nextval('public.depart_tb_dept_no_seq'::regclass);


--
-- Name: enroll_schedule_tb id; Type: DEFAULT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.enroll_schedule_tb ALTER COLUMN id SET DEFAULT nextval('public.enroll_schedule_tb_id_seq'::regclass);


--
-- Name: enroll_tb enroll_no; Type: DEFAULT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.enroll_tb ALTER COLUMN enroll_no SET DEFAULT nextval('public.enroll_tb_enroll_no_seq'::regclass);


--
-- Name: grade_tb id; Type: DEFAULT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.grade_tb ALTER COLUMN id SET DEFAULT nextval('public.grade_tb_id_seq'::regclass);


--
-- Name: lecture_tb lecture_id; Type: DEFAULT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.lecture_tb ALTER COLUMN lecture_id SET DEFAULT nextval('public.lecture_tb_lecture_id_seq'::regclass);


--
-- Name: overenroll_tb over_no; Type: DEFAULT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.overenroll_tb ALTER COLUMN over_no SET DEFAULT nextval('public.overenroll_tb_over_no_seq'::regclass);


--
-- Name: schedule_tb sche_no; Type: DEFAULT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.schedule_tb ALTER COLUMN sche_no SET DEFAULT nextval('public.schedule_tb_sche_no_seq'::regclass);


--
-- Name: user_tb user_no; Type: DEFAULT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.user_tb ALTER COLUMN user_no SET DEFAULT nextval('public.user_tb_user_no_seq'::regclass);


--
-- Name: depart_tb depart_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.depart_tb
    ADD CONSTRAINT depart_tb_pkey PRIMARY KEY (dept_no);


--
-- Name: enroll_schedule_tb enroll_schedule_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.enroll_schedule_tb
    ADD CONSTRAINT enroll_schedule_tb_pkey PRIMARY KEY (id);


--
-- Name: enroll_tb enroll_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.enroll_tb
    ADD CONSTRAINT enroll_tb_pkey PRIMARY KEY (enroll_no);


--
-- Name: grade_tb grade_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.grade_tb
    ADD CONSTRAINT grade_tb_pkey PRIMARY KEY (id);


--
-- Name: lecture_tb lecture_tb_course_no_key; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.lecture_tb
    ADD CONSTRAINT lecture_tb_course_no_key UNIQUE (course_no);


--
-- Name: lecture_tb lecture_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.lecture_tb
    ADD CONSTRAINT lecture_tb_pkey PRIMARY KEY (lecture_id);


--
-- Name: notice_tb notice_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.notice_tb
    ADD CONSTRAINT notice_tb_pkey PRIMARY KEY (id);


--
-- Name: notification_tb notification_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.notification_tb
    ADD CONSTRAINT notification_tb_pkey PRIMARY KEY (id);


--
-- Name: overenroll_tb overenroll_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.overenroll_tb
    ADD CONSTRAINT overenroll_tb_pkey PRIMARY KEY (over_no);


--
-- Name: schedule_tb schedule_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.schedule_tb
    ADD CONSTRAINT schedule_tb_pkey PRIMARY KEY (sche_no);


--
-- Name: system_config_tb system_config_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.system_config_tb
    ADD CONSTRAINT system_config_tb_pkey PRIMARY KEY (key);


--
-- Name: user_tb user_tb_email_key; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.user_tb
    ADD CONSTRAINT user_tb_email_key UNIQUE (email);


--
-- Name: user_tb user_tb_loginid_key; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.user_tb
    ADD CONSTRAINT user_tb_loginid_key UNIQUE (loginid);


--
-- Name: user_tb user_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.user_tb
    ADD CONSTRAINT user_tb_pkey PRIMARY KEY (user_no);


--
-- Name: waitlist_tb waitlist_tb_pkey; Type: CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.waitlist_tb
    ADD CONSTRAINT waitlist_tb_pkey PRIMARY KEY (id);


--
-- Name: ix_grade_tb_enrollment_id; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_grade_tb_enrollment_id ON public.grade_tb USING btree (enrollment_id);


--
-- Name: ix_grade_tb_user_id; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_grade_tb_user_id ON public.grade_tb USING btree (user_id);


--
-- Name: ix_lecture_tb_department; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_lecture_tb_department ON public.lecture_tb USING btree (department);


--
-- Name: ix_lecture_tb_lec_grade; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_lecture_tb_lec_grade ON public.lecture_tb USING btree (lec_grade);


--
-- Name: ix_lecture_tb_type; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_lecture_tb_type ON public.lecture_tb USING btree (type);


--
-- Name: ix_notification_tb_user_id; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_notification_tb_user_id ON public.notification_tb USING btree (user_id);


--
-- Name: ix_user_tb_user_name; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_user_tb_user_name ON public.user_tb USING btree (user_name);


--
-- Name: ix_waitlist_tb_created_at; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_waitlist_tb_created_at ON public.waitlist_tb USING btree (created_at);


--
-- Name: ix_waitlist_tb_lecture_id; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_waitlist_tb_lecture_id ON public.waitlist_tb USING btree (lecture_id);


--
-- Name: ix_waitlist_tb_user_id; Type: INDEX; Schema: public; Owner: mugang
--

CREATE INDEX ix_waitlist_tb_user_id ON public.waitlist_tb USING btree (user_id);


--
-- Name: enroll_tb enroll_tb_lecture_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.enroll_tb
    ADD CONSTRAINT enroll_tb_lecture_id_fkey FOREIGN KEY (lecture_id) REFERENCES public.lecture_tb(lecture_id);


--
-- Name: enroll_tb enroll_tb_loginid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.enroll_tb
    ADD CONSTRAINT enroll_tb_loginid_fkey FOREIGN KEY (loginid) REFERENCES public.user_tb(user_no);


--
-- Name: grade_tb grade_tb_enrollment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.grade_tb
    ADD CONSTRAINT grade_tb_enrollment_id_fkey FOREIGN KEY (enrollment_id) REFERENCES public.enroll_tb(enroll_no) ON DELETE CASCADE;


--
-- Name: grade_tb grade_tb_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.grade_tb
    ADD CONSTRAINT grade_tb_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_tb(user_no) ON DELETE CASCADE;


--
-- Name: lecture_tb lecture_tb_dept_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.lecture_tb
    ADD CONSTRAINT lecture_tb_dept_no_fkey FOREIGN KEY (dept_no) REFERENCES public.depart_tb(dept_no);


--
-- Name: notice_tb notice_tb_author_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.notice_tb
    ADD CONSTRAINT notice_tb_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.user_tb(user_no);


--
-- Name: notification_tb notification_tb_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.notification_tb
    ADD CONSTRAINT notification_tb_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_tb(user_no) ON DELETE CASCADE;


--
-- Name: overenroll_tb overenroll_tb_lecture_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.overenroll_tb
    ADD CONSTRAINT overenroll_tb_lecture_id_fkey FOREIGN KEY (lecture_id) REFERENCES public.lecture_tb(lecture_id) ON DELETE CASCADE;


--
-- Name: overenroll_tb overenroll_tb_sche_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.overenroll_tb
    ADD CONSTRAINT overenroll_tb_sche_no_fkey FOREIGN KEY (sche_no) REFERENCES public.schedule_tb(sche_no) ON DELETE SET NULL;


--
-- Name: overenroll_tb overenroll_tb_user_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.overenroll_tb
    ADD CONSTRAINT overenroll_tb_user_no_fkey FOREIGN KEY (user_no) REFERENCES public.user_tb(user_no) ON DELETE CASCADE;


--
-- Name: schedule_tb schedule_tb_lecture_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.schedule_tb
    ADD CONSTRAINT schedule_tb_lecture_id_fkey FOREIGN KEY (lecture_id) REFERENCES public.lecture_tb(lecture_id) ON DELETE CASCADE;


--
-- Name: user_tb user_tb_dept_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.user_tb
    ADD CONSTRAINT user_tb_dept_no_fkey FOREIGN KEY (dept_no) REFERENCES public.depart_tb(dept_no) ON DELETE SET NULL;


--
-- Name: waitlist_tb waitlist_tb_lecture_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.waitlist_tb
    ADD CONSTRAINT waitlist_tb_lecture_id_fkey FOREIGN KEY (lecture_id) REFERENCES public.lecture_tb(lecture_id) ON DELETE CASCADE;


--
-- Name: waitlist_tb waitlist_tb_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mugang
--

ALTER TABLE ONLY public.waitlist_tb
    ADD CONSTRAINT waitlist_tb_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_tb(user_no) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict glDwmuf30CuiyDX7bcrRDO5aq2AUcPor1IsDbpgBHgMXmsh1kZ4HOrtP5Oad6sL

