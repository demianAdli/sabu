"""
Sabu project
jug_lca_buildings package
input_geojson_content module
Returns a temporary path to input the GeometryFactory
Project Designer and Developer: Alireza Adli
Licensed under the Apache License, Version 2.0.
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import tempfile
import json
import logging


logger = logging.getLogger(__name__)


class InputGeoJsonContent:
  def __init__(self, content):
    self.content = content

  @property
  def content(self):
    return self._content

  @property
  def is_temp_file(self):
    return self._is_temp_file

  def _write_temp_geojson(self, content):
    try:
      temp_file = tempfile.NamedTemporaryFile(
        delete=False, suffix='.geojson', mode='w', encoding='utf8')
      try:
        json.dump(content, temp_file)
        temp_file.flush()
        self._content = temp_file.name
        self._is_temp_file = True
        logger.debug('GeoJSON temporary file created.')
      finally:
        temp_file.close()
    except (OSError, TypeError) as e:
      raise ValueError(
        'Invalid GeoJSON content: could not serialize to JSON'
      ) from e

  @content.setter
  def content(self, content):
    self._is_temp_file = False
    if isinstance(content, str):
      content = content.strip()
      if content.startswith('{') or content.startswith('['):
        logger.debug('GeoJSON input detected as JSON string.')
        try:
          parsed_obj = json.loads(content)
        except json.JSONDecodeError:
          # Not valid JSON; keep current behavior and treat as a file path.
          self._content = content
        else:
          # Valid JSON string; persist to a temporary GeoJSON file.
          self._write_temp_geojson(parsed_obj)
      else:
        self._content = content
    else:
      self._write_temp_geojson(content)
