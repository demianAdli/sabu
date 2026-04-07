"""
scrub_layer_class module
PyQGIS functionalities that are needed in the cleaning and updating
Montreal Buildings dataset project, gathered in one class.
Project Developer: Alireza Adli alireza.adli@concordia.ca
"""
import glob
import os
import shutil
import tempfile

import processing

from qgis.core import QgsApplication, QgsField, QgsProject, \
  QgsProcessingFeedback, QgsVectorLayer, QgsVectorDataProvider, \
  QgsExpressionContext, QgsExpressionContextUtils, edit, QgsFeatureRequest, \
  QgsExpression, QgsVectorFileWriter, QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QVariant
from qgis.analysis import QgsNativeAlgorithms

from .basic_functions import create_folders, find_shp_files


class ScrubLayer:
  def __init__(self, qgis_path, layer_path, layer_name):

    self.qgis_path = qgis_path
    # Set the path to QGIS installation
    QgsApplication.setPrefixPath(self.qgis_path, True)

    self.layer_path = layer_path
    self.layer_name = layer_name
    self.layer = self.load_layer()
    self.data_count = self.layer.featureCount()

  def duplicate_layer(self, output_path):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'ESRI Shapefile'

    duplication = QgsVectorFileWriter.writeAsVectorFormat(
      self.layer,
      output_path,
      options
    )

    if duplication == QgsVectorFileWriter.NoError:
      print(f"Shapefile successfully duplicated")
    else:
      print(f"Error duplicating shapefile: {duplication}")

  def get_cell(self, fid, field_name):
    return self.layer.getFeature(fid)[field_name]

  def select_cells(
          self,
          field_name, field_value, required_field,
          return_one_value=False):
    """Returns the value of a field
    based on the value of another field in the same record"""
    expression = QgsExpression(f'{field_name} = {field_value}')
    request = QgsFeatureRequest(expression)
    features = self.layer.getFeatures(request)
    field_field_values = []
    for feature in features:
      field_field_values.append(feature[required_field])
      if return_one_value and field_field_values:
        return field_field_values[0]
    return field_field_values

  def load_layer(self):
    the_layer = QgsVectorLayer(self.layer_path, self.layer_name, 'ogr')
    if not the_layer.isValid():
      raise ValueError(
        f'Failed to load layer {self.layer_name} from {self.layer_path}')
    else:
      QgsProject.instance().addMapLayer(the_layer)
    return the_layer

  def features_to_layers(self, layers_dir, crs):
    create_folders(layers_dir, self.data_count)
    target_crs = QgsCoordinateReferenceSystem(crs)
    for feature in self.layer.getFeatures():
      new_layer = QgsVectorLayer(
        f'Polygon?crs={crs}', "feature_layer", "memory")
      new_layer.setCrs(target_crs)

      new_provider = new_layer.dataProvider()
      new_provider.addFeatures([feature])

      feature_id = feature.id()
      output_path = f'{layers_dir}layer_{feature_id}/layer_{feature_id}.shp'

      QgsVectorFileWriter.writeAsVectorFormat(
        new_layer,
        output_path,
        'utf-8',
        new_layer.crs(),
        'ESRI Shapefile'
      )
    print('Shapefiles created for each feature.')

  def fix_geometries(self, fixed_layer):
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    fix_geometries_params = {
      'INPUT': self.layer,
      'METHOD': 0,
      'OUTPUT': fixed_layer
    }
    processing.run("native:fixgeometries", fix_geometries_params)

  def create_spatial_index(self):
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    create_spatial_index_params = {
      'INPUT': self.layer,
      'OUTPUT': 'Output'
    }
    processing.run("native:createspatialindex", create_spatial_index_params)
    print(f'Creating Spatial index for {self.layer_name} is completed.')

  def spatial_join(self, joining_layer_path, joined_layer_path):
    """In QGIS, it is called 'Join attributes by Location'"""
    params = {'INPUT': self.layer,
              'PREDICATE': [0],
              'JOIN': joining_layer_path,
              'JOIN_FIELDS': [],
              'METHOD': 0,
              'DISCARD_NONMATCHING': False,
              'PREFIX': '',
              'OUTPUT': joined_layer_path}

    feedback = QgsProcessingFeedback()
    processing.run(
      'native:joinattributesbylocation', params, feedback=feedback)
    print(f'Spatial Join with input layer {self.layer_name} is completed.')

  @staticmethod
  def _replace_layer_files(source_path, destination_path):
    source_base, source_ext = os.path.splitext(source_path)
    destination_base, destination_ext = os.path.splitext(destination_path)

    if source_ext.lower() != destination_ext.lower():
      raise ValueError(
        f'Cannot replace layer {destination_path} with {source_path} '
        f'because their formats differ.')

    if destination_ext.lower() == '.shp':
      for existing_file in glob.glob(f'{destination_base}.*'):
        os.remove(existing_file)

      for source_file in glob.glob(f'{source_base}.*'):
        extension = os.path.splitext(source_file)[1]
        shutil.move(source_file, f'{destination_base}{extension}')
      return

    if os.path.exists(destination_path):
      os.remove(destination_path)
    shutil.move(source_path, destination_path)

  def field_join(
          self,
          joining_layer_path,
          joining_layer_name,
          target_field,
          join_field,
          join_fields=None,
          prefix='',
          output_path=None):
    """Joins fields from another layer and persists the result.

    If output_path is None, the current layer dataset is replaced in place.
    If join_fields is None, all fields from the joining layer are added.
    """
    joining_layer = QgsVectorLayer(
      joining_layer_path, joining_layer_name, 'ogr')
    if not joining_layer.isValid():
      raise ValueError(
        f'Failed to load layer {joining_layer_name} '
        f'from {joining_layer_path}')

    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

    final_output_path = output_path or self.layer_path
    temp_dir = None
    processing_output_path = final_output_path

    if final_output_path == self.layer_path:
      temp_dir = tempfile.mkdtemp(prefix='field_join_')
      layer_extension = os.path.splitext(self.layer_path)[1]
      processing_output_path = os.path.join(
        temp_dir, f'{self.layer_name}{layer_extension}')

    params = {
      'INPUT': self.layer,
      'FIELD': target_field,
      'INPUT_2': joining_layer,
      'FIELD_2': join_field,
      'FIELDS_TO_COPY': join_fields or [],
      'METHOD': 1,
      'DISCARD_NONMATCHING': False,
      'PREFIX': prefix,
      'OUTPUT': processing_output_path
    }

    processing.run('native:joinattributestable', params)

    if final_output_path == self.layer_path:
      old_layer_id = self.layer.id()
      QgsProject.instance().removeMapLayer(old_layer_id)
      self._replace_layer_files(processing_output_path, self.layer_path)
      shutil.rmtree(temp_dir)
      self.layer = self.load_layer()
      self.data_count = self.layer.featureCount()

    print(
      f'Field Join of {self.layer_name} with input layer '
      f'{joining_layer_name} is completed.')

  def clip_layer(self, overlay_layer, clipped_layer):
    """This must be tested"""
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    clip_layer_params = {
      'INPUT': self.layer_path,
      'OVERLAY': overlay_layer,
      'FILTER_EXPRESSION': '',
      'FILTER_EXTENT': None,
      'OUTPUT': clipped_layer
    }
    processing.run("native:clip", clip_layer_params)
    print(f'Clipping of {self.layer_name} is completed.')

  def clip_by_predefined_zones(self):
    pass

  def clip_by_multiple(
          self, number_of_partitions, overlay_layers_dir, clipped_layers_dir):
    create_folders(clipped_layers_dir, number_of_partitions)
    for layer in range(number_of_partitions):
      overlay = overlay_layers_dir + f'/layer_{layer}/layer_{layer}.shp'
      clipped = clipped_layers_dir + f'/layer_{layer}/layer_{layer}.shp'
      self.clip_layer(overlay, clipped)
      clipped_layer = ScrubLayer(self.qgis_path, clipped, 'Temp Layer')
      clipped_layer.create_spatial_index()

  def split_layer(self, number_of_layers, splitted_layers_dir):
    number_of_layers -= 1
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    create_folders(splitted_layers_dir, number_of_layers)
    intervals = self.data_count // number_of_layers
    for part in range(number_of_layers):
      output_layer_path = \
        splitted_layers_dir + f'/layer_{part}/layer_{part}.shp'
      params = {'INPUT': self.layer,
                'EXPRESSION': f'$id >= {part * intervals} '
                              f'AND $id < {(part + 1) * intervals}\r\n',
                'OUTPUT': output_layer_path}

      processing.run("native:extractbyexpression", params)

      new_layer = ScrubLayer(self.qgis_path, output_layer_path, 'Temp Layer')
      new_layer.create_spatial_index()

    # Adding a folder for the remaining features

    os.makedirs(splitted_layers_dir + f'/layer_{number_of_layers}')
    output_layer_path = splitted_layers_dir + \
        f'/layer_{number_of_layers}/layer_{number_of_layers}.shp'
    params = {'INPUT': self.layer,
              'EXPRESSION': f'$id >= {number_of_layers * intervals}\r\n',
              'OUTPUT': output_layer_path}

    processing.run("native:extractbyexpression", params)
    new_layer = ScrubLayer(self.qgis_path, output_layer_path, 'Temp Layer')
    new_layer.create_spatial_index()

  @staticmethod
  def merge_layers(layers_path, mergeded_layer_path):
    merging_layers = find_shp_files(layers_path)
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

    params = {'LAYERS': merging_layers,
              'CRS': None,
              'OUTPUT': mergeded_layer_path}

    processing.run("native:mergevectorlayers", params)

  def multipart_to_singleparts(self, singleparts_layer_path):
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    params = {'INPUT': self.layer,
              'OUTPUT': singleparts_layer_path}
    processing.run("native:multiparttosingleparts", params)

  def delete_duplicates(self, deleted_duplicates_layer):
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    params = {'INPUT': self.layer_path,
              'OUTPUT': deleted_duplicates_layer}
    processing.run("native:deleteduplicategeometries", params)

  def delete_field(self, field_name):
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    with edit(self.layer):
      # Get the index of the column to delete
      idx = self.layer.fields().indexFromName(field_name)

      # Delete the field
      self.layer.deleteAttribute(idx)

      # Update layer fields
      self.layer.updateFields()

  def delete_record_by_index(self, record_index):
    self.layer.startEditing()

    if self.layer.deleteFeature(record_index):
      print(f'Feature with ID {record_index} has been successfully removed.')
    else:
      print(f'Failed to remove feature with ID {record_index}.')

    self.layer.commitChanges()

  def conditional_delete_record(self, field_name, operator, condition):
    if isinstance(condition, str) and condition.upper() != 'NULL':
      condition = f"'{condition}'"
    else:
      condition = str(condition)

    request = QgsFeatureRequest().setFilterExpression(
      f'"{field_name}" {operator} {condition}')
    with edit(self.layer):
      for feature in self.layer.getFeatures(request):
        self.layer.deleteFeature(feature.id())

  def add_field(self, new_field_name):
    functionalities = self.layer.dataProvider().capabilities()

    if functionalities & QgsVectorDataProvider.AddAttributes:
      new_field = QgsField(new_field_name, QVariant.Double)
      self.layer.dataProvider().addAttributes([new_field])
      self.layer.updateFields()

  def assign_area(self, field_name):
    self.layer.startEditing()
    idx = self.layer.fields().indexFromName(field_name)

    context = QgsExpressionContext()
    context.appendScopes(
      QgsExpressionContextUtils.globalProjectLayerScopes(self.layer))

    for feature in self.layer.getFeatures():
      area = feature.geometry().area()
      feature[idx] = area
      self.layer.updateFeature(feature)

    self.layer.commitChanges()

  def __str__(self):
    return f'The {self.layer_name} has {self.data_count} records.'

  @staticmethod
  def cleanup():
    QgsApplication.exitQgis()
