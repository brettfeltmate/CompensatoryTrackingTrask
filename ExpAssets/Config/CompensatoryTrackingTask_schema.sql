CREATE TABLE participants (
    id integer primary key autoincrement not null,
    userhash text not null,
    gender text not null,
    age integer not null, 
    handedness text not null,
    created text not null
);

CREATE TABLE trials (
    id integer primary key autoincrement not null,
    participant_id integer not null references participants(id),
    block_num integer not null,
    trial_num integer not null
);

CREATE TABLE comp_track_data (
    id integer primary key autoincrement not null,
    participant_id integer not null references participants(id),
    timestamp text not null,
    buffeting_force text not null,
    additional_force text not null,
    total_force text not null,
    user_input text not null,
    target_position text not null,
    displacement text not null,
    PVT_event text not null,
    PVT_RT text not null
)