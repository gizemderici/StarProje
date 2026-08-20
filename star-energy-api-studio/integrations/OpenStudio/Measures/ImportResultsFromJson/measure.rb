require 'json'
require 'openstudio'
require 'openstudio/measure/ShowRunnerOutput'

class ImportResultsFromJson < OpenStudio::Measure::ModelMeasure
  def name
    'Import Results From Json'
  end

  def description
    'Reads Python-generated JSON results and applies simple updates to the active OpenStudio model.'
  end

  def modeler_description
    'Demonstrates how to push external analysis results back into the active model.'
  end

  def arguments(model)
    args = OpenStudio::Measure::OSArgumentVector.new

    input_path = OpenStudio::Measure::OSArgument.makeStringArgument('input_path', true)
    input_path.setDisplayName('Input Results JSON Path')
    input_path.setDefaultValue('C:/star_proje/out/analysis_results.json')
    args << input_path

    args
  end

  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)
    return false unless runner.validateUserArguments(arguments(model), user_arguments)

    input_path = runner.getStringArgumentValue('input_path', user_arguments)
    input_file = File.expand_path(input_path)

    unless File.exist?(input_file)
      runner.registerError("Results JSON not found: #{input_file}")
      return false
    end

    results = JSON.parse(File.read(input_file))
    recommendations = results.fetch('recommendations', [])

    applied_count = 0

    recommendations.each do |item|
      next unless item['type'] == 'space_tag'

      target_space = model.getSpaces.find { |space| space.nameString == item['target_name'] }
      next unless target_space

      if item['field'] == 'comment'
        target_space.setComment(item['value'].to_s)
        applied_count += 1
      end
    end

    runner.registerFinalCondition("Applied #{applied_count} updates from #{input_file}")
    true
  rescue StandardError => e
    runner.registerError("Import failed: #{e.message}")
    runner.registerError(e.backtrace.join("\n"))
    false
  end
end

ImportResultsFromJson.new.registerWithApplication
