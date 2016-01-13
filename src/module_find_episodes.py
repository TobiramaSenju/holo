from logging import debug, info, error

import services
import reddit

debug_no_submit = False

def main(config, db, **kwargs):
	reddit.init_reddit(config)
	
	# Check services for new episodes
	for service in db.get_services(enabled=True):
		streams = db.get_streams(service=service)
		service_handler = services.get_service_handler(service)
		debug("{} streams found".format(len(streams)))
		for stream in streams:
			info("Checking stream \"{}\"".format(stream.site_key))
			debug(stream)
			
			# Check latest episode
			episode = service_handler.get_latest_episode(stream.site_key, useragent=config.useragent)
			debug(episode)
			info("  Is live: {}".format(episode.is_live))
			
			if episode.is_live:
				# Adjust episode number with offset and check if already in database
				episode_num = episode.number - stream.remote_offset
				info("  Adjusted num: {}".format(episode_num))
				already_seen = db.stream_has_episode(stream, episode_num)
				info("  Already seen: {}".format(already_seen))
				
				# New episode!
				if not already_seen:
					post_url = _create_reddit_post(config, db, stream, episode, submit=not debug_no_submit)
					info("  Post URL: {}".format(post_url))
					if post_url is not None:
						db.store_episode(stream.show, episode_num, post_url)
					else:
						error("  Episode not submitted")

def _create_reddit_post(config, db, stream, episode, submit=True):
	title, body = _create_post_contents(config, db, stream, episode)
	if submit:
		new_post = reddit.submit_text_post(config.subreddit, title, body)
		if new_post is not None:
			debug("Post successful")
			return reddit.get_shortlink_from_id(new_post.id)
		else:
			error("Failed to submit post")
	return None

def _create_post_contents(config, db, stream, episode):
	show = db.get_show(stream=stream)
	
	debug("Formatting with formats:")
	debug(config.post_formats)
	title = _format_post_text(db, config.post_title, config.post_formats, show, episode, stream)
	info("Title:\n"+title)
	body = _format_post_text(db, config.post_body, config.post_formats, show, episode, stream)
	info("Body:\n"+body)
	return title, body

def _format_post_text(db, text, formats, show, episode, stream):
	episode_num = episode.number + stream.display_offset
	
	if "{spoiler}" in text:
		text = safe_format(text, spoiler=_gen_text_spoiler(formats, show))
	if "{streams}" in text:
		text = safe_format(text, streams=_gen_text_streams(db, formats, show))
	text = safe_format(text, show_name=show.name, episode=episode_num, episode_name=episode.name)
	return text.strip()

# Generating text parts

def _gen_text_spoiler(formats, show):
	if show.has_source:
		return formats["spoiler"]
	return ""

def _gen_text_streams(db, formats, show):
	streams = db.get_streams(show=show)
	stream_texts = list()
	for stream in streams:
		if stream.active:
			service = db.get_service(id=stream.service)
			if service.enabled:
				service_handler = services.get_service_handler(service)
				
				text = formats["stream"]
				text = safe_format(text, service_name=service.name, stream_link=service_handler.get_stream_link(stream))
				stream_texts.append(text)
	
	return "\n".join(stream_texts)

# Helpers

class _SafeDict(dict):
	def __missing__(self, key):
		return "{"+key+"}"

def safe_format(s, **kwargs):
	return s.format_map(_SafeDict(**kwargs))
