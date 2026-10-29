---
name: <% tp.file.title %>
relationship:
role:
location:
birthdate:
address:
phone:
email:
tags:
  - person
image:
banner: "Media/Banners/Note Types/person-note.gif"
banner-height: 200
banner-y: 50
---

<!-- Template: uses Templater (tp.* expressions run on insert; set Templates folder to Templates). Delete this comment in the finished note. -->
<!-- relationship: me (your own note), coworker, manager, family, friend or other. role is the team for
coworkers. The profile card below reads the Notes bullets (Role, Team, Slack, Timezone, Pronouns);
Team and Slack are markdown links, Timezone an IANA zone such as America/Chicago. image: a quoted
wiki-link to a picture file stored under Media/. -->

# <% tp.file.title %>

[[People/People Hub|People Hub]]

```dataviewjs
await dv.view("Templates/Views/person-profile")
```

> [!abstract] Overview
> Who they are to you, and what to remember about them.

## Together

> [!multi-column]
>
> > [!note]+ Meetings
> > ![[Meetings/Meetings.base#Linked to this note]]
>
> > [!todo]+ Open tasks
> >
> > ```tasks
> > not done
> > description includes [[<% tp.file.title %>]]
> > sort by due
> > short mode
> > ```

## Log

Newest first. Dated moments worth remembering: what they said, plans, gifts, follow-ups.

### #<% tp.date.now("YYYY-MM-DD") %> - <% tp.date.now("dddd") %>

- Added the note.

## Notes

- **Role:**
- **Team:**
- **Slack:**
- **Timezone:**
- **Pronouns:**

## Mentioned in

<!-- Anything else that links here: projects, events, documents, wiki notes. Meetings and daily notes are excluded. -->

```base
filters:
  and:
    - file.hasLink(this.file)
    - '!file.inFolder("Meetings")'
    - '!file.inFolder("Daily Notes")'
    - '!file.inFolder("Templates")'
views:
  - type: table
    name: Mentioned in
    order:
      - file.name
      - type
      - summary
    sort:
      - property: file.mtime
        direction: DESC
    limit: 10
```
