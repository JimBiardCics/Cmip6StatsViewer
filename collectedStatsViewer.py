from matplotlib import pyplot

import ipywidgets as widgets
import netCDF4
import numpy
import os
import sys
import warnings

warnings.simplefilter('ignore')


class StatsViewer(object):
    def __init__(self, inputFile):
        dataset = netCDF4.Dataset(inputFile, 'r')

        self.models      = [ 'all' ] + [ x for x in dataset.variables['model_names'][...] ]
        self.scenarios   = [ 'all' ] + [ x for x in dataset.variables['scenario_names'][...] ]
        self.yearRanges  = [ 'all' ] + [ x for x in dataset.variables['year_ranges'][...] ]

        self.seasons = [ x for x in dataset.variables['season_names'][...] ]
        self.months  = [ x for x in dataset.variables['month_names'][...] ]

        self.clims  = [ 'all seasons', 'all months' ] + self.seasons + self.months

        self.yearBounds  = dataset.variables['year_bounds'][...]
        self.monthlyClim  = dataset.variables['monthly_clim'][...]
        self.seasonalClim = dataset.variables['seasonal_clim'][...]

        self.monthlyValues = dataset.variables['monthly_clim']
        self.monthlyStdevs = dataset.variables['monthly_clim_stdev']

        self.seasonalValues = dataset.variables['seasonal_clim'][...]
        self.seasonalStdevs = dataset.variables['seasonal_clim_stdev'][...]

        self.valueUnits = dataset.variables['seasonal_clim'].units

        self.figure, self.axes = pyplot.subplots()


    def displayChart(self, climsSelected, modelsSelected, scenariosSelected, rangesSelected, xAxisSelected, yAxisSelected):
        # Build the data selection.
        #
        if 'all seasons' == climsSelected[0]:
            climsSelected = list(self.seasons)
            theClims      = self.seasons
            values        = self.seasonalValues
            stdevs        = self.seasonalStdevs
        elif 'all months' == climsSelected[0]:
            climsSelected = list(self.months)
            theClims      = self.months
            values        = self.monthlyValues
            stdevs        = self.monthlyStdevs
        elif set(climsSelected) <= set(self.seasons):
            theClims = self.seasons
            values   = self.seasonalValues
            stdevs   = self.seasonalStdevs
        elif set(climsSelected) <= set(self.months):
            theClims = self.months
            values   = self.monthlyValues
            stdevs   = self.monthlyStdevs
        else:
            raise ValueError('Selecting a mix of months and seasons is forbidden')

        if 'all' == modelsSelected[0]:
            modelsSelected = list(self.models[1:])

        if 'all' == scenariosSelected[0]:
            scenariosSelected = list(self.scenarios[1:])
        
        if 'all' == rangesSelected[0]:
            rangesSelected = list(self.yearRanges[1:])
        
        if 'values' != yAxisSelected:
            scenariosSelected = list(scenariosSelected)

            try:
                scenariosSelected.remove('historical')
            except:
                pass

        shape = (
            len(modelsSelected),
            len(scenariosSelected),
            len(rangesSelected),
            len(climsSelected)
        )
        
        indices = ( [], [], [], [] )
        
        for model in modelsSelected:
            modelIndex = self.models.index(model) - 1
            
            for scenario in scenariosSelected:
                scenarioIndex = self.scenarios.index(scenario) - 1
                
                for yearRange in rangesSelected:
                    rangeIndex = self.yearRanges.index(yearRange) - 1
                    
                    for clim in climsSelected:
                        climIndex = theClims.index(clim) - 1
                    
                        indices[0].append(modelIndex)
                        indices[1].append(scenarioIndex)
                        indices[2].append(rangeIndex)
                        indices[3].append(climIndex)

        names = [ modelsSelected, scenariosSelected, rangesSelected, climsSelected ]

        plotValues = values[indices].reshape(shape)
        
        if 'values' != yAxisSelected:
            indices = ( [], [], [], [] )

            scenarioIndex = self.scenarios.index('historical') - 1

            for model in modelsSelected:
                modelIndex = self.models.index(model) - 1

                for yearRange in self.yearRanges[1:]:
                    rangeIndex = self.yearRanges.index(yearRange) - 1
                    
                    if 0 == values[modelIndex, scenarioIndex, rangeIndex].count():
                        continue

                    for clim in climsSelected:
                        climIndex = theClims.index(clim) - 1

                        indices[0].append(modelIndex)
                        indices[1].append(scenarioIndex)
                        indices[2].append(rangeIndex)
                        indices[3].append(climIndex)        

            historicalShape = (
                len(modelsSelected),
                1,
                1,
                len(climsSelected)
            )
            
            historicalValues = values[indices].reshape(historicalShape)

            counts = historicalValues.count(axis = (0, 1, 3))

            historicalValues = historicalValues.compress(counts > 0, axis = 2)

            
            plotValues /= historicalValues
            
        xAxisOptions = ('models', 'scenarios', 'years', 'climatology time')
        
        xAxisIndex = xAxisOptions.index(xAxisSelected)
        
        xLabels = list(names.pop(xAxisIndex))
        
        dimensions = [ x for x in range(0, plotValues.ndim) ]
        
        del dimensions[xAxisIndex]
        
        dimensions.append(xAxisIndex)
        
        plotValues = plotValues.transpose(dimensions)
        
        numBarsInGroup = numpy.prod(plotValues.shape[0:-1])
        numGroups      = plotValues.shape[-1]
        
        plotValues = plotValues.reshape((numBarsInGroup, numGroups))
        
        barLabels = list()

        for name0 in names[0]:
            for name1 in names[1]:
                for name2 in names[2]:
                     barLabels.append(' '.join((name0, name1, name2)))

        counts = plotValues.count(axis = 1)
        
        plotValues = plotValues.compress(counts > 0, axis = 0)
        
        empties = numpy.where(counts == 0)[0]
        
        for index in empties[-1::-1]:
            del barLabels[index]
        
        counts = plotValues.count(axis = 0)

        plotValues = plotValues.compress(counts > 0, axis = 1)
        
        empties = numpy.where(counts == 0)[0]
        
        for index in empties[-1::-1]:
            del xLabels[index]
        
        numBarsInGroup = plotValues.shape[0]
        numGroups      = plotValues.shape[1]
        
        barGroupWidth = 0.75
        barWidth      = barGroupWidth / float(numBarsInGroup)
        
        barLocations  = numpy.arange(0, plotValues.size, dtype = float).reshape((numBarsInGroup, numGroups))
        barLocations %= numGroups
        
        barGroupCenters = barLocations[0].copy()

        barOffsets  = numpy.arange(0, numBarsInGroup, dtype = float).reshape((numBarsInGroup, 1))
        barOffsets -= (numBarsInGroup - 1) / 2.0
        barOffsets *= barWidth
        
        barLocations += barOffsets

        self.axes.cla()
        
        plotMax = 1.05 * plotValues.max()
        plotMin = 0.95 * plotValues.min()
        
        self.axes.set_ylim(bottom = plotMin, top = plotMax)

        for label, xs, ys in zip(barLabels, barLocations[:], plotValues[:]):
        
            self.axes.bar(xs, ys, barWidth, label = label)
        
        plotUnits = self.valueUnits
        
        if 'values' != yAxisSelected:
            plotUnits = 'future/historical'
            
        self.axes.set_ylabel(plotUnits)
        self.axes.set_xticks(barGroupCenters)
     
        xTickLabels = self.axes.set_xticklabels(xLabels)

        self.axes.legend(bbox_to_anchor = (1.04, 0.0), loc = 'lower left', borderaxespad = 0)

        self.figure.subplots_adjust(right = 0.5, bottom = 0.2)

        pyplot.setp(xTickLabels, rotation=45, ha="right", rotation_mode="anchor")
