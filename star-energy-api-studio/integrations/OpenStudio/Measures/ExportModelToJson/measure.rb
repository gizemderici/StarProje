require 'json'
require 'fileutils'
require 'openstudio'
require 'openstudio/measure/ShowRunnerOutput'

class ExportModelToJson < OpenStudio::Measure::ModelMeasure
  def name
    'Export Model To Json'
  end

  def description
    'Exports the currently open OpenStudio model to a JSON file for external Python processing.'
  end

  def modeler_description
    'Collects a subset of model data from the active model and writes it to JSON.'
  end

  def arguments(model)
    args = OpenStudio::Measure::OSArgumentVector.new

    output_path = OpenStudio::Measure::OSArgument.makeStringArgument('output_path', true)
    output_path.setDisplayName('Output JSON Path')
    output_path.setDefaultValue('C:/star_proje/out/model_export.json')
    args << output_path

    args
  end

  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)
    return false unless runner.validateUserArguments(arguments(model), user_arguments)

    output_path = runner.getStringArgumentValue('output_path', user_arguments)
    output_file = File.expand_path(output_path)
    FileUtils.mkdir_p(File.dirname(output_file))

    payload = {
      metadata: {
        building_name: model.getBuilding.nameString,
        space_count: model.getSpaces.size,
        thermal_zone_count: model.getThermalZones.size,
        surface_count: model.getSurfaces.size,
        subsurface_count: model.getSubSurfaces.size
      },
      spaces: model.getSpaces.map do |space|
        {
          name: space.nameString,
          floor_area_m2: safe_double(space.floorArea),
          volume_m3: safe_double(space.volume),
          thermal_zone: space.thermalZone.is_initialized ? space.thermalZone.get.nameString : nil
        }
      end,
      thermal_zones: model.getThermalZones.map do |zone|
        {
          name: zone.nameString,
          space_names: zone.spaces.map(&:nameString)
        }
      end
    }

    File.write(output_file, JSON.pretty_generate(payload))
    runner.registerInfo("JSON export created: #{output_file}")
    runner.registerFinalCondition("Exported #{payload[:spaces].size} spaces and #{payload[:thermal_zones].size} thermal zones.")
    true
  rescue StandardError => e
    runner.registerError("Export failed: #{e.message}")
    runner.registerError(e.backtrace.join("\n"))
    false
  end

  private

  def safe_double(value)
    return nil if value.nil?

    value.to_f
  end
end

ExportModelToJson.new.registerWithApplication
