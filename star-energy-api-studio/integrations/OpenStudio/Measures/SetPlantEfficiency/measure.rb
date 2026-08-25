class SetPlantEfficiency < OpenStudio::Measure::ModelMeasure
  def name
    'Set Plant Efficiency'
  end

  def description
    'Sets the chiller reference COP and the hot water boiler nominal thermal efficiency.'
  end

  def modeler_description
    'Updates every OS:Chiller:Electric:EIR and OS:Boiler:HotWater in the model. ' \
      'Performance curves are left untouched; only the rated points move.'
  end

  def arguments(_model)
    args = OpenStudio::Measure::OSArgumentVector.new

    cop = OpenStudio::Measure::OSArgument.makeDoubleArgument('chiller_cop', true)
    cop.setDisplayName('Chiller reference COP (W/W)')
    cop.setDefaultValue(5.5)
    args << cop

    efficiency = OpenStudio::Measure::OSArgument.makeDoubleArgument('boiler_efficiency', true)
    efficiency.setDisplayName('Boiler nominal thermal efficiency')
    efficiency.setDefaultValue(0.9)
    args << efficiency

    args
  end

  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)
    return false unless runner.validateUserArguments(arguments(model), user_arguments)

    cop = runner.getDoubleArgumentValue('chiller_cop', user_arguments)
    efficiency = runner.getDoubleArgumentValue('boiler_efficiency', user_arguments)

    if cop <= 0
      runner.registerError('Chiller COP must be greater than zero.')
      return false
    end
    unless efficiency.positive? && efficiency <= 1.0
      runner.registerError('Boiler efficiency must be between 0 and 1.')
      return false
    end

    chillers = model.getChillerElectricEIRs
    boilers = model.getBoilerHotWaters

    if chillers.empty? && boilers.empty?
      runner.registerError('No chiller or boiler found in the model.')
      return false
    end

    initial = []
    chillers.each do |chiller|
      initial << "#{chiller.nameString} COP #{chiller.referenceCOP.round(3)}"
      chiller.setReferenceCOP(cop)
    end
    boilers.each do |boiler|
      current = boiler.nominalThermalEfficiency
      initial << "#{boiler.nameString} efficiency #{current.round(3)}"
      boiler.setNominalThermalEfficiency(efficiency)
    end

    runner.registerInitialCondition(initial.join('; '))
    runner.registerValue('chiller_cop', cop, 'W/W')
    runner.registerValue('boiler_efficiency', efficiency)
    runner.registerFinalCondition(
      "Set COP #{cop} on #{chillers.length} chiller(s) and efficiency " \
        "#{efficiency} on #{boilers.length} boiler(s)."
    )
    true
  rescue StandardError => e
    runner.registerError("Set Plant Efficiency failed: #{e.message}")
    false
  end
end

SetPlantEfficiency.new.registerWithApplication
